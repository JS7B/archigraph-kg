# Audit Scope Maintenance Implementation Plan

> **For agentic workers:** Use TDD and keep this worktree limited to `.codex/hooks/`, its tests, and the DEVLOG/audit documentation.

**Goal:** Make the project Hook audit the new `feat/kg-*` worktrees instead of silently skipping their backend gates.

**Architecture:** Extend the existing deterministic path-to-command map. Each new branch gets an exact scope tuple and each backend area gets a targeted pytest command using the Hook interpreter. Existing frontend/evaluation/audit behavior and fail-closed JSON behavior remain unchanged.

## Global Constraints

- Work only in `D:\AgenX\archigraph-kg-audit-scope` on `feat/audit-scope`.
- Do not modify business code, graph schema, frontend, or `tasks/todo.md`.
- Use TDD; no LLM, Neo4j, npm build, or network access is required for the audit tests.
- The final tree must not track `.superpowers` reports.

### Task 1: Add new branch scopes and targeted backend gates

**Files:**
- Modify: `.codex/hooks/audit_gate.py`
- Test: `backend/tests/audit/test_audit_gate.py`
- Modify: `docs/audit-workflow.md`
- Modify: `docs/DEVLOG.md`

**Interfaces:**

```python
PYTHON_PARSING_COMMAND = [sys.executable, "-m", "pytest", "backend/tests/parsing", "-q"]
PYTHON_EXTRACTION_COMMAND = [sys.executable, "-m", "pytest", "backend/tests/extraction", "-q"]
PYTHON_GRAPH_COMMAND = [sys.executable, "-m", "pytest", "backend/tests/graph", "backend/tests/routers/test_graph.py", "-q"]
```

Add exact `BRANCH_SCOPES` for `feat/kg-parsing`, `feat/kg-extraction`, `feat/kg-resolution`, `feat/kg-community-api`, and `feat/kg-graph-experience`. `commands_for_paths` must select the narrow backend command for parsing, extraction, graph/router, and frontend paths. A path outside the exact branch scope must still block.

- [ ] Add RED tests for each new branch scope and for each targeted command selection.
- [ ] Run `D:\Anaconda\envs\myself\python.exe -m pytest backend/tests/audit/test_audit_gate.py -q` and observe the expected assertion failures.
- [ ] Implement the constants, scope map, command selection, and docs with no unrelated refactor.
- [ ] Run the audit tests, `git diff --check`, and a manual clean parsing-repo audit that returns `{"continue": true}`.
- [ ] Commit `chore(audit): cover graph quality worktrees`.
