# Graph Experience Implementation Plan

**Goal:** 把前端从一次性全图渲染升级为社区/局部图优先、证据可见、稳定布局和可访问详情的工作台。

**Branch:** `feat/graph-experience` in `D:\AgenX\archigraph-kg-graph-experience`.

## Constraints

- 继续 Cytoscape，不引入新的图可视化库；复用现有 UI 组件和设计 token。
- 后端真实 API 状态驱动加载/错误/展开，不用前端伪造社区或 Agent 状态。
- 默认请求有界 local subgraph/community，不再依赖全图作为唯一视图；保留旧 API fallback。
- 任务只修改 `frontend/src/`、前端测试和 `frontend/DEVLOG.md`。

## Task 1: API/types and local-first state

- Add typed clients for communities/subgraph/evidence and map `evidenceChunkId`.
- Change GraphView to community/center selection with bounded expansion and loading/error states.
- Tests cover mapping and request query parameters.

## Task 2: stable graph rendering and evidence detail

- Use stable layout inputs/positions across local expansions; style nodes by type/community and edges by confidence.
- Add evidence panel showing edge evidence chunk ID, document ID, and relation metadata; missing evidence is explicit.
- Keep keyboard-accessible entity list and selected-node focus.

## Task 3: visual QA and learning log

- Add focused component tests for community overview, expand/collapse, error/empty states, and evidence panel.
- Add five-field `frontend/DEVLOG.md` entry explaining local-first rendering and stable layout choices.
- Run lint/typecheck/test/build and Hook.

## Acceptance

- Initial view is bounded and navigable; user can expand a center node without full-graph reload.
- Selected node/edge details show provenance or explicit missing evidence.
- Layout does not reshuffle solely because a filter toggles; existing keyboard list remains usable.
- Frontend unit tests, lint, typecheck, build pass.
