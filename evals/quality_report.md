# 人工复核质量夹具报告

> 这是小型、确定性的人工复核夹具基线，不能替代真实模型基线或生产图谱快照。

## 样本覆盖

- 夹具文档数：2
- 选择方法：手工夹具切片候选全集，人工正确性部分复核
- accepted 实体人工复核覆盖：80.0% (8/10)
- accepted 关系人工复核覆盖：83.3% (5/6)

## 人工复核指标

| 指标 | 结果 | 口径 |
|---|---:|---|
| 实体 precision | 87.5% (7/8) | 仅计 accepted 且已有人工正确/错误标签的实体 |
| 关系 semantic precision | 80.0% (4/5) | 仅计 accepted 且已人工判断方向、类型和语义的关系 |
| provenance completeness | 100.0% (16/16) | 夹具中全部 accepted 实体与关系 |

未命中不自动算错；尚未人工定性的 accepted 项保留为 review candidate，并从 precision 分母排除：

- 实体：api::run-event, overview::personal-graph
- 关系：api::drives

## Accepted 图结构诊断

- 孤立实体：3（api::chunk, overview::fake-tool, overview::personal-graph）
- 度为 1 的实体：3（api::neo4j, api::run-event, overview::vector-index）
- 低置信关系（confidence < 0.6）：2（api::queries, overview::system-uses-vector）
- 跨文档 normalized-name 重复：neo4j (api-contract/graph-rag-overview)
- 连通组件规模分布：1 节点 × 3, 3 节点 × 1, 4 节点 × 1
- 疑似泛化 hub（度 ≥ 3）：overview::system

## 限制

- 本报告不调用 LLM 或 Neo4j，只证明指标定义、分母和结构诊断可复现。
- precision 只代表已人工复核的夹具样本，必须连同上方覆盖率阅读。
- `evals/report.md` 仍是 2026-07-03 的真实模型历史快照，本报告不会覆盖它。
