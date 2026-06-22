"""问答编排：串起全链，只保留答案里真实出现的角标 citation，confidence 计算。"""

from app.graph.search import ChunkHit
from app.qa import pipeline as pipeline_mod
from app.qa.models import RelationPath, RetrievalContext
from app.qa.pipeline import answer_question


def _hit(i: int) -> ChunkHit:
    return ChunkHit(
        chunk_id=f"d#{i}", document_id="d", chunk_index=i, text=f"片段{i}",
        char_start=i, char_end=i + 1, score=1.0,
    )


def _patch_chain(monkeypatch, *, answer_text: str):
    monkeypatch.setattr(pipeline_mod.llm, "embed", lambda texts: [[0.1] * 8])
    monkeypatch.setattr(
        pipeline_mod, "search_chunks",
        lambda d, v, *, top_k, database: [_hit(0), _hit(1), _hit(2)],
    )
    monkeypatch.setattr(
        pipeline_mod, "rerank_chunks",
        lambda q, chunks, *, top_n: chunks[:top_n],
    )
    monkeypatch.setattr(
        pipeline_mod, "expand_entities",
        lambda d, ids, *, database: RetrievalContext(paths=[]),
    )
    monkeypatch.setattr(pipeline_mod.llm, "chat", lambda messages: answer_text)


def test_only_cited_chunks_kept(monkeypatch):
    # 答案只引用了 [1] 和 [3]
    _patch_chain(monkeypatch, answer_text="知识图谱是… [1]。它支持检索 [3]。")
    ans = answer_question(None, "问题")
    indices = {c.index for c in ans.citations}
    assert indices == {1, 3}


def test_confidence_high_when_multiple_citations(monkeypatch):
    _patch_chain(monkeypatch, answer_text="结论 [1][2]。")
    ans = answer_question(None, "问题")
    assert ans.confidence == "high"


def test_confidence_low_when_no_citation(monkeypatch):
    _patch_chain(monkeypatch, answer_text="根据现有资料无法回答。")
    ans = answer_question(None, "问题")
    assert ans.confidence == "low"
    assert ans.citations == []


def test_empty_recall_returns_low(monkeypatch):
    monkeypatch.setattr(pipeline_mod.llm, "embed", lambda texts: [[0.1] * 8])
    monkeypatch.setattr(
        pipeline_mod, "search_chunks", lambda d, v, *, top_k, database: []
    )
    ans = answer_question(None, "问题")
    assert ans.confidence == "low"
    assert ans.citations == []
