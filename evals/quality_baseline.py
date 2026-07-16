"""Build a deterministic report from the manually reviewed quality fixtures."""

from dataclasses import dataclass
from pathlib import Path

from evals.quality_fixtures import QualityFixture, load_quality_fixtures
from evals.quality_metrics import (
    RatioMetric,
    StructuralDiagnostics,
    entity_review_candidate_ids,
    graph_structure_diagnostics,
    relation_review_candidate_ids,
    summarize_entity_precision,
    summarize_entity_review_coverage,
    summarize_provenance_completeness,
    summarize_relation_review_coverage,
    summarize_relation_semantic_precision,
)


DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.6
DEFAULT_GENERIC_NAMES = {"system", "系统", "平台", "工具"}
DEFAULT_HUB_DEGREE_THRESHOLD = 3


@dataclass(frozen=True)
class QualityBaseline:
    sample_count: int
    selection_methods: tuple[str, ...]
    entity_precision: RatioMetric
    relation_semantic_precision: RatioMetric
    provenance_completeness: RatioMetric
    entity_review_coverage: RatioMetric
    relation_review_coverage: RatioMetric
    entity_review_candidates: tuple[str, ...]
    relation_review_candidates: tuple[str, ...]
    structure: StructuralDiagnostics


def build_quality_baseline(fixtures: list[QualityFixture]) -> QualityBaseline:
    return QualityBaseline(
        sample_count=len(fixtures),
        selection_methods=tuple(
            dict.fromkeys(row.review_scope.selection_method for row in fixtures)
        ),
        entity_precision=summarize_entity_precision(fixtures),
        relation_semantic_precision=summarize_relation_semantic_precision(fixtures),
        provenance_completeness=summarize_provenance_completeness(fixtures),
        entity_review_coverage=summarize_entity_review_coverage(fixtures),
        relation_review_coverage=summarize_relation_review_coverage(fixtures),
        entity_review_candidates=entity_review_candidate_ids(fixtures),
        relation_review_candidates=relation_review_candidate_ids(fixtures),
        structure=graph_structure_diagnostics(
            fixtures,
            low_confidence_threshold=DEFAULT_LOW_CONFIDENCE_THRESHOLD,
            generic_names=DEFAULT_GENERIC_NAMES,
            hub_degree_threshold=DEFAULT_HUB_DEGREE_THRESHOLD,
        ),
    )


def _format_ratio(metric: RatioMetric) -> str:
    rate = "n/a" if metric.rate is None else f"{metric.rate:.1%}"
    return f"{rate} ({metric.numerator}/{metric.denominator})"


def _format_ids(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "无"


def render_quality_report(baseline: QualityBaseline) -> str:
    structure = baseline.structure
    components = ", ".join(
        f"{size} 节点 × {count}"
        for size, count in structure.component_size_distribution.items()
    ) or "无"
    duplicate_names = ", ".join(
        f"{name} ({'/'.join(documents)})"
        for name, documents in structure.duplicate_normalized_names.items()
    ) or "无"
    methods = "；".join(baseline.selection_methods) or "未声明"
    return "\n".join(
        [
            "# 人工复核质量夹具报告",
            "",
            "> 这是小型、确定性的人工复核夹具基线，不能替代真实模型基线或生产图谱快照。",
            "",
            "## 样本覆盖",
            "",
            f"- 夹具文档数：{baseline.sample_count}",
            f"- 选择方法：{methods}",
            f"- accepted 实体人工复核覆盖：{_format_ratio(baseline.entity_review_coverage)}",
            f"- accepted 关系人工复核覆盖：{_format_ratio(baseline.relation_review_coverage)}",
            "",
            "## 人工复核指标",
            "",
            "| 指标 | 结果 | 口径 |",
            "|---|---:|---|",
            f"| 实体 precision | {_format_ratio(baseline.entity_precision)} | 仅计 accepted 且已有人工正确/错误标签的实体 |",
            f"| 关系 semantic precision | {_format_ratio(baseline.relation_semantic_precision)} | 仅计 accepted 且已人工判断方向、类型和语义的关系 |",
            f"| provenance completeness | {_format_ratio(baseline.provenance_completeness)} | 夹具中全部 accepted 实体与关系 |",
            "",
            "未命中不自动算错；尚未人工定性的 accepted 项保留为 review candidate，并从 precision 分母排除：",
            "",
            f"- 实体：{_format_ids(baseline.entity_review_candidates)}",
            f"- 关系：{_format_ids(baseline.relation_review_candidates)}",
            "",
            "## Accepted 图结构诊断",
            "",
            f"- 孤立实体：{len(structure.isolated_entity_ids)}（{_format_ids(structure.isolated_entity_ids)}）",
            f"- 度为 1 的实体：{len(structure.degree_one_entity_ids)}（{_format_ids(structure.degree_one_entity_ids)}）",
            f"- 低置信关系（confidence < {DEFAULT_LOW_CONFIDENCE_THRESHOLD}）：{len(structure.low_confidence_relation_ids)}（{_format_ids(structure.low_confidence_relation_ids)}）",
            f"- 跨文档 normalized-name 重复：{duplicate_names}",
            f"- 连通组件规模分布：{components}",
            f"- 疑似泛化 hub（度 ≥ {DEFAULT_HUB_DEGREE_THRESHOLD}）：{_format_ids(structure.suspicious_generic_hub_ids)}",
            "",
            "## 限制",
            "",
            "- 本报告不调用 LLM 或 Neo4j，只证明指标定义、分母和结构诊断可复现。",
            "- precision 只代表已人工复核的夹具样本，必须连同上方覆盖率阅读。",
            "- `evals/report.md` 仍是 2026-07-03 的真实模型历史快照，本报告不会覆盖它。",
            "",
        ]
    )


def main() -> None:
    report_path = Path(__file__).with_name("quality_report.md")
    report_path.write_text(
        render_quality_report(build_quality_baseline(load_quality_fixtures())),
        encoding="utf-8",
    )
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
