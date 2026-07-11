# Knowledge Graph Entity Resolution Implementation Plan

**Goal:** 在不把相似词强行合并的前提下，为跨文档实体提供可解释的 canonical identity、别名和解析证据。

**Branch:** `feat/kg-resolution` in `D:\AgenX\archigraph-kg-resolution`.

## Constraints

- 先用确定性规则：Unicode/大小写/空白规范化、显式别名、稳定 exact key；模糊匹配只产生 review，不直接 accepted。
- 每次解析保留 source entity id、canonical id、方法、分数和理由；无法安全解析则保持文档内实体，不丢数据。
- 不引入新的向量库或 LLM；复用现有 Pydantic 与 extraction models。
- 任务只修改 `backend/app/resolution/`、对应 tests 和 `backend/DEVLOG.md`，不改 parser/extraction writer/API/frontend。

## Task 1: resolution contract

- Add `ResolutionStatus`, `ResolutionMethod`, `ResolutionEvidence`, `ResolutionCandidate` models.
- Define canonical entity references and alias records with source document/chunk provenance.
- Tests cover serialization, confidence bounds, and safe defaults.

## Task 2: deterministic resolver

- Implement exact normalized key and explicit alias lookup.
- Unicode punctuation/whitespace/case normalization must be deterministic and idempotent.
- Candidate fuzzy similarity may return `review` below a configurable high threshold; never auto-merge ambiguous ties.
- Tests cover FastAPI/Fast API/fastapi aliases, Chinese/English case, collisions, and ambiguous candidates.

## Task 3: resolution diagnostics and integration adapter

- Add a pure adapter that consumes `MergedEntity` records and returns canonical groups plus evidence without writing Neo4j.
- Preserve document-scoped fallback IDs and mention provenance.
- Add DEVLOG entry describing why exact-first and review-before-merge is safer than LLM autonomous merging.

## Acceptance

- Exact/explicit alias resolution is deterministic and explainable.
- Ambiguous similarity never silently merges.
- Every accepted resolution has evidence; unresolved items remain queryable.
- Resolution unit tests, py_compile, diff-check, and branch Hook pass.
