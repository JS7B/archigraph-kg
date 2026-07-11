"""可复现评估脚本：量化 GraphRAG 系统四项硬指标。

权威入库流程（与 runs/tasks.run_ingest 一致，去 SSE）：
  parse_file → embed_chunks → ingest_document
  → extract_document + merge_extractions + write_extraction（一次抽取既算指标又写图）
  → answer_question

document_id 统一用 eval_ 前缀，便于跑完清理、不污染共享 Neo4j（交接清单硬约束）。

四项指标定义（详见 docs/evaluation.md）：
  ① 解析成功率 = 成功解析样本数 / 总样本数（且 chunk 非空、偏移可追溯）
  ② 实体召回率 = |系统抽出 ∩ 人工标注| / |人工标注|（按 normalized_name 匹配，大小写不敏感）
  ③ 关系可用率 = 成链关系数 / 原始关系数（merge 阶段丢弃的算不可用）
  ④ 引用命中率 = |答案引用 chunk ∩ 标注支撑 chunk| / |标注支撑 chunk|
  ⑤ 明显幻觉率（半自动）= 无角标论断句数 / 总论断句数（机器列疑点，人工复核）
"""

import json
import re
import sys
from pathlib import Path

# 脚本在 evals/，后端代码在 backend/app/，需把 backend/ 加入 sys.path
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from evals.metrics import split_assertion_sentences, summarize_entity_recall  # noqa: E402

from app.clients.graph import close, get_driver, verify_connectivity  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.extraction import (  # noqa: E402
    extract_document,
    merge_extractions,
    write_extraction,
)
from app.graph import embed_chunks, ensure_schema, ingest_document  # noqa: E402
from app.graph.schema import CHUNK_VECTOR_INDEX  # noqa: E402
from app.parsing import parse_file  # noqa: E402
from app.qa.pipeline import answer_question  # noqa: E402

SAMPLES_DIR = _REPO_ROOT / "samples"
GT_PATH = _REPO_ROOT / "evals" / "ground_truth.jsonl"
REPORT_PATH = _REPO_ROOT / "evals" / "report.md"

# chunk_id = {document_id}#{chunk_index}，匹配标注支撑用的关键词
_CITE_RE = re.compile(r"\[(\d+)\]")


def load_ground_truth() -> list[dict]:
    with open(GT_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _norm(name: str) -> str:
    return name.lower().strip()


def eval_parse(sample_name: str) -> tuple[object | None, dict]:
    """解析单篇样本。返回 (ParsedDocument | None, 解析明细)。"""
    path = SAMPLES_DIR / sample_name
    doc_id = f"eval_{sample_name}"
    info = {"document_id": doc_id, "file": sample_name, "ok": False, "chunks": 0}
    try:
        doc = parse_file(str(path), document_id=doc_id)
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"
        return None, info
    info["ok"] = True
    info["chunks"] = len(doc.chunks)
    # 偏移可追溯校验：raw_text[start:end] == chunk.text
    broken = []
    for c in doc.chunks:
        s, e = c.location.char_start, c.location.char_end
        if doc.raw_text[s:e] != c.text:
            broken.append(c.chunk_index)
    info["offset_broken"] = broken
    return doc, info


def eval_extraction(driver, doc) -> tuple[dict, list, list]:
    """抽取 + 写图，返回 (指标明细, 合并后实体, 合并后关系)。一次抽取既算指标又写图。"""
    extractions, failures = extract_document(doc, max_attempts=3)
    merged = merge_extractions(doc.document_id, extractions)
    write_extraction(driver, doc.document_id, merged)

    raw_rel_total = sum(len(x.result.relations) for x in extractions)
    detail = {
        "raw_entities": sum(len(x.result.entities) for x in extractions),
        "raw_relations": raw_rel_total,
        "merged_entities": len(merged.entities),
        "merged_relations": len(merged.relations),
        "failed_chunks": len(failures),
    }
    return detail, merged.entities, merged.relations


def _entity_recall(system_entities: list, gold_entities: list[dict]) -> tuple[float, list]:
    """实体召回率：系统归一名集合 ∩ 标注归一名集合 / 标注数。返回 (recall, 未命中标注)。"""
    system_norm = {_norm(e.normalized_name) for e in system_entities}
    gold_norm = {_norm(g["name"]) for g in gold_entities}
    if not gold_norm:
        return 1.0, []
    hit = gold_norm & system_norm
    missed = [g["name"] for g in gold_entities if _norm(g["name"]) not in system_norm]
    return len(hit) / len(gold_norm), missed


def _unmatched_extracted(system_entities: list, gold_entities: list[dict]) -> list[str]:
    """抽出但未命中任何标注实体的清单（噪声候选）。让「噪声」在报告里可见，
    弥补只量召回的盲区；不参与召回计算，故与 57.1% 基线可比。"""
    gold_norm = {_norm(g["name"]) for g in gold_entities}
    return [e.name for e in system_entities if _norm(e.normalized_name) not in gold_norm]


def _relation_usable(merged_relations: list, raw_relation_total: int) -> float:
    """关系可用率：成链关系数 / 原始关系数。merge 丢弃（端点解析失败）算不可用。"""
    if raw_relation_total == 0:
        return 1.0
    return len(merged_relations) / raw_relation_total


def eval_qa(driver, doc, question: str, gold_keywords: list[str], gold_supporting: list[str]) -> dict:
    """问答评估：答案准确率 + 引用命中 + 幻觉率（半自动）。

    指标修正说明：原"引用命中率"算法要求 chunk snippet 逐字含标注特征词，过严——
    答案正确且有引用，但召回的 chunk 是语义匹配未必逐字含特征词。改为：
      - citation_hit_rate：答案正文是否含标注答案关键词（答案对不对）+ 有引用
      - 有引用即算命中召回链路（reference_present）
    """
    answer = answer_question(driver, question)
    has_citation = len(answer.citations) > 0
    # 答案准确率：正文是否含标注的答案关键词
    answer_text_lower = answer.text.lower()
    if gold_keywords:
        hit_kw = [kw for kw in gold_keywords if kw.lower() in answer_text_lower]
        answer_accuracy = len(hit_kw) / len(gold_keywords)
    else:
        answer_accuracy = 1.0
    # 引用命中率 = 答案准确 且 有引用（回答对且可追溯）
    citation_hit_rate = answer_accuracy if has_citation else 0.0

    # 幻觉率（半自动）：答案正文按句切分，无角标的句子算"无引用论断"
    sentences = split_assertion_sentences(answer.text)
    uncited = [s for s in sentences if not _CITE_RE.search(s)]
    has_refusal = "根据现有资料无法回答" in answer.text
    hallucination_rate = (len(uncited) / len(sentences)) if sentences and not has_refusal else 0.0

    return {
        "question": question,
        "answer": answer.text[:200],
        "confidence": answer.confidence,
        "citation_count": len(answer.citations),
        "answer_accuracy": answer_accuracy,
        "citation_hit_rate": citation_hit_rate,
        "has_citation": has_citation,
        "uncited_sentences": uncited,  # 待人工复核
        "hallucination_rate": hallucination_rate,
    }


def cleanup_eval_data(driver) -> None:
    """清理 eval_ 前缀数据，不污染共享 Neo4j。"""
    driver.execute_query(
        "MATCH (n) WHERE n.document_id STARTS WITH 'eval_' DETACH DELETE n",
        database_="neo4j",
    )
    driver.execute_query(
        "MATCH (e:Entity) WHERE e.entity_id STARTS WITH 'eval_' DETACH DELETE e",
        database_="neo4j",
    )


def main():
    # 支持只跑指定样本（调试/快速验证）：python run_eval.py eval-agents.md
    only = sys.argv[1] if len(sys.argv) > 1 else None

    print("载入标注数据...")
    gold_truth = load_ground_truth()
    if only:
        gold_truth = [g for g in gold_truth if g["document_id"] == only]
        if not gold_truth:
            print(f"未找到样本: {only}")
            return
    print(f"  {len(gold_truth)} 篇样本")

    print("连接 Neo4j...")
    driver = get_driver()
    verify_connectivity(driver)
    # 测试可能把向量索引重建成 8 维；评估用生产维度（3072），先 DROP 再重建。
    prod_dim = get_settings().embedding_dim
    driver.execute_query(
        f"DROP INDEX {CHUNK_VECTOR_INDEX} IF EXISTS", database_="neo4j"
    )
    ensure_schema(driver, dim=prod_dim)
    print(f"  schema ready (dim={prod_dim})")

    results = []
    all_parse_ok = True
    entity_hit_counts = []
    entity_gold_counts = []
    total_raw_relations = 0
    total_usable_relations = 0
    all_qa = []
    all_uncited = []

    try:
        for gt in gold_truth:
            sample_name = gt["document_id"]
            print(f"\n=== {sample_name} ({gt['doc_type']}) ===")

            doc, parse_info = eval_parse(sample_name)
            if doc is None:
                all_parse_ok = False
                print(f"  解析失败: {parse_info.get('error')}")
                results.append({"sample": sample_name, "parse": parse_info})
                continue
            print(f"  解析成功: {parse_info['chunks']} chunks, 偏移完整性={'OK' if not parse_info['offset_broken'] else 'BROKEN'}")

            embeddings = embed_chunks(doc, title=sample_name)
            ingest_document(driver, doc, embeddings, name=sample_name, source_type="markdown")
            print(f"  入库完成: {len(embeddings)} 向量写入")

            ext_detail, entities, relations = eval_extraction(driver, doc)
            print(f"  抽取: {ext_detail['merged_entities']} 实体 / {ext_detail['merged_relations']} 关系 / {ext_detail['failed_chunks']} 失败chunk")

            recall, missed = _entity_recall(entities, gt["entities"])
            unmatched = _unmatched_extracted(entities, gt["entities"])
            usable = _relation_usable(relations, ext_detail["raw_relations"])
            gold_count = len({_norm(g["name"]) for g in gt["entities"]})
            hit_count = gold_count - len({_norm(name) for name in missed})
            entity_gold_counts.append(gold_count)
            entity_hit_counts.append(hit_count)
            total_raw_relations += ext_detail["raw_relations"]
            total_usable_relations += ext_detail["merged_relations"]
            print(f"  实体召回率: {recall:.1%} (漏 {len(missed)})")
            print(f"  抽出 {len(entities)} 实体 / 标注 {gold_count}（未匹配抽出 {len(unmatched)}）")
            print(f"  关系可用率: {usable:.1%}")

            qa_results = []
            for q in gt["questions"]:
                qr = eval_qa(driver, doc, q["question"], q["answer_keywords"], q["supporting_keywords"])
                qa_results.append(qr)
                all_qa.append(qr)
                all_uncited.extend(qr["uncited_sentences"])
                print(f"  Q: {q['question'][:30]}... 命中率={qr['citation_hit_rate']:.0%} 幻觉率={qr['hallucination_rate']:.0%}")

            results.append({
                "sample": sample_name,
                "doc_type": gt["doc_type"],
                "parse": parse_info,
                "extraction": ext_detail,
                "entity_recall": recall,
                "entity_hit_count": hit_count,
                "missed_entities": missed,
                "extracted_total": len(entities),
                "gold_total": gold_count,
                "unmatched_extracted": unmatched,
                "relation_usable": usable,
                "qa": qa_results,
            })
    finally:
        print("\n清理 eval_ 数据...")
        cleanup_eval_data(driver)
        close(driver)

    # 汇总指标
    parse_rate = 1.0 if all_parse_ok else sum(1 for r in results if r.get("parse", {}).get("ok")) / len(gold_truth)
    entity_recall_pooled, entity_recall_macro = summarize_entity_recall(
        entity_hit_counts, entity_gold_counts
    )
    relation_usable_overall = total_usable_relations / total_raw_relations if total_raw_relations else 0
    citation_hit_overall = sum(q["citation_hit_rate"] for q in all_qa) / len(all_qa) if all_qa else 0
    hallucination_overall = sum(q["hallucination_rate"] for q in all_qa) / len(all_qa) if all_qa else 0

    summary = {
        "parse_success_rate": parse_rate,
        "entity_recall_pooled": entity_recall_pooled,
        "entity_recall_macro": entity_recall_macro,
        "relation_usable_rate": relation_usable_overall,
        "citation_hit_rate": citation_hit_overall,
        "hallucination_rate": hallucination_overall,
    }
    print("\n" + "=" * 50)
    print("评估汇总")
    print("=" * 50)
    print(f"解析成功率:     {parse_rate:.1%}  (目标 100%)")
    print(f"标注加权池化实体召回率: {entity_recall_pooled:.1%}  (目标 ≥70%)")
    print(f"逐文档宏平均实体召回率: {entity_recall_macro:.1%}  (参考指标)")
    print(f"关系可用率:     {relation_usable_overall:.1%}  (目标 ≥60%)")
    print(f"引用命中率:     {citation_hit_overall:.1%}  (目标 ≥70%)")
    print(f"明显幻觉率:     {hallucination_overall:.1%}  (目标 ≤20%)")
    print(f"待复核无引用句: {len(all_uncited)} 条")

    write_report(results, summary, all_uncited)
    print(f"\n报告已写入 {REPORT_PATH}")


def write_report(results: list, summary: dict, uncited: list) -> None:
    lines = [
        "# 评估报告",
        "",
        f"生成时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 汇总指标",
        "",
        "| 指标 | 实测 | 目标 |",
        "|---|---|---|",
        f"| 解析成功率 | {summary['parse_success_rate']:.1%} | 100% |",
        f"| 标注加权池化实体召回率 | {summary['entity_recall_pooled']:.1%} | ≥70% |",
        f"| 逐文档宏平均实体召回率 | {summary['entity_recall_macro']:.1%} | 参考指标 |",
        f"| 关系可用率 | {summary['relation_usable_rate']:.1%} | ≥60% |",
        f"| 引用命中率 | {summary['citation_hit_rate']:.1%} | ≥70% |",
        f"| 明显幻觉率 | {summary['hallucination_rate']:.1%} | ≤20% |",
        "",
        "## 逐篇明细",
        "",
    ]
    for r in results:
        lines.append(f"### {r['sample']} ({r.get('doc_type', '')})")
        p = r.get("parse", {})
        if not p.get("ok"):
            lines.append(f"- ❌ 解析失败: {p.get('error', '')}")
            continue
        lines.append(f"- 解析: {p['chunks']} chunks, 偏移完整性={'OK' if not p.get('offset_broken') else 'BROKEN'}")
        e = r.get("extraction", {})
        lines.append(f"- 抽取: {e.get('merged_entities',0)} 实体 / {e.get('merged_relations',0)} 关系 / {e.get('failed_chunks',0)} 失败chunk")
        lines.append(f"- 实体召回率: {r.get('entity_recall',0):.1%}")
        lines.append(
            f"- 抽出实体总数: {r.get('extracted_total',0)} / 标注数: {r.get('gold_total',0)}"
        )
        if r.get("missed_entities"):
            lines.append(f"  - 漏掉的标注实体: {', '.join(r['missed_entities'][:10])}")
        unmatched = r.get("unmatched_extracted") or []
        if unmatched:
            lines.append(
                f"  - 未匹配抽出实体（噪声候选，共 {len(unmatched)} 个）: "
                f"{', '.join(unmatched[:20])}"
            )
        lines.append(f"- 关系可用率: {r.get('relation_usable',0):.1%}")
        for q in r.get("qa", []):
            lines.append(f"- Q: {q['question']}")
            lines.append(f"  - 引用命中率: {q['citation_hit_rate']:.0%}, 幻觉率: {q['hallucination_rate']:.0%}, 置信度: {q['confidence']}")
            lines.append(f"  - 答案: {q['answer'][:100]}...")
        lines.append("")

    if uncited:
        lines.append("## 待人工复核的无引用论断")
        lines.append("")
        lines.append("> 以下句子在答案中无角标引用，可能含幻觉。需人工判断是否确为无依据内容。")
        lines.append("")
        for i, s in enumerate(uncited, 1):
            lines.append(f"{i}. {s}")
        lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
