# Knowledge Graph Community and Local-Graph API Plan

**Goal:** 在现有 Neo4j 查询基础上提供局部邻域、社区概览、证据字段和稳定过滤契约，给前端从“全图机械铺开”转为“先概览、再展开”。

**Branch:** `feat/kg-community-api` in `D:\AgenX\archigraph-kg-community-api`.

## Constraints

- 继续使用 Neo4j；不引入新的图数据库或重型社区计算框架。
- 查询只返回 accepted Entity/RELATES 数据及其 evidence_chunk_id；不改变 writer schema。
- 局部图必须有节点/边数量上限、中心节点和过滤参数，避免前端一次拉全库。
- 单元测试使用 fake driver；Neo4j integration tests 仍按现有 fixture 单独运行。

## Task 1: response contract and local subgraph

- Add Pydantic response models for graph nodes/edges/evidence and local subgraph metadata.
- Add a bounded `/api/graph/entities/{entity_id}/subgraph` endpoint with depth, limit, type and confidence filters.
- Ensure missing center returns 404 and evidence fields are preserved.

## Task 2: community overview

- Add a deterministic community overview endpoint using connected components/relationship density from Neo4j query results; no LLM summaries in this task.
- Return stable community IDs, representative nodes, counts and optional document IDs.
- Add fake-driver API tests and bounded query assertions.

## Task 3: evidence/document filters and API learning log

- Extend search/list/local graph responses with document filter and evidence references without breaking existing fields.
- Add five-field DEVLOG entry explaining local-first graph queries and why limits/filters are correctness and UX safeguards.
- Run graph/router unit tests, py_compile, diff-check, and Hook.

## Acceptance

- Local graph API never returns unbounded full graph.
- Every returned edge has type/confidence/evidence chunk ID when stored.
- Community overview is deterministic and stable for the same graph snapshot.
- Existing `/entities`, `/neighbors`, `/search` contracts remain compatible.
