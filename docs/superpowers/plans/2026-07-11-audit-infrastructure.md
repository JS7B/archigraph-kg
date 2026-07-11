# Audit Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic branch audit that Codex Stop/SubagentStop hooks and the main reviewer can both invoke without committing, merging, pushing, or calling real LLM services.

**Architecture:** Put pure path-to-command policy in a Python module, expose hook JSON responses through a small CLI, and configure repo-local lifecycle hooks. The script audits only `feat/*`; `main` always passes because merge authority stays with the main reviewer.

**Tech Stack:** Python 3.12 standard library, pytest, Codex project hooks, Git, npm.

## Global Constraints

- Work only on `feat/audit-infrastructure` in `D:\AgenX\archigraph-kg-audit`.
- Never read or print `.env`; never call real LLM; never commit, merge, push, or modify another worktree.
- Hook failures may request continuation once; `stop_hook_active=true` must pass to prevent loops.
- Update `docs/DEVLOG.md`; do not edit `tasks/todo.md` or merge to main.

---

### Task 1: Build a testable audit policy

**Files:**
- Create: `.codex/hooks/__init__.py`
- Create: `.codex/hooks/audit_gate.py`
- Create: `backend/tests/audit/test_audit_gate.py`

**Interfaces:**
- Produces: `changed_paths(repo: Path, base: str = "main") -> list[str]`.
- Produces: `commands_for_paths(paths: list[str]) -> list[list[str]]`.
- Produces: `hook_decision(branch: str, stop_hook_active: bool, failures: list[str]) -> dict`.

- [ ] **Step 1: Write failing policy tests**

```python
def test_frontend_paths_select_all_frontend_gates():
    commands = commands_for_paths(["frontend/src/App.tsx"])
    rendered = [" ".join(command) for command in commands]
    assert any("npm run lint" in command for command in rendered)
    assert any("npm run typecheck" in command for command in rendered)
    assert any("npm run test:run" in command for command in rendered)
    assert any("npm run build" in command for command in rendered)


def test_active_stop_hook_never_blocks_again():
    assert hook_decision("feat/audit", True, ["failed"])["continue"] is True


def test_failed_feature_audit_requests_continuation():
    result = hook_decision("feat/audit", False, ["pytest failed"])
    assert result["decision"] == "block"
    assert "pytest failed" in result["reason"]
```

- [ ] **Step 2: Prove the module is missing**

Run: `conda run -n myself python -m pytest backend/tests/audit/test_audit_gate.py -q`

Expected: import failure.

- [ ] **Step 3: Implement policy and command execution**

Use `git diff --name-only main...HEAD`, unstaged diff, and cached diff to collect paths. Deduplicate while preserving order. Select commands by path:

```python
FRONTEND_COMMANDS = [
    ["npm", "run", "lint"],
    ["npm", "run", "typecheck"],
    ["npm", "run", "test:run"],
    ["npm", "run", "build"],
]
EVAL_COMMANDS = [
    ["conda", "run", "-n", "myself", "python", "-m", "pytest", "evals/tests", "-q"],
]
AUDIT_COMMANDS = [
    ["conda", "run", "-n", "myself", "python", "-m", "pytest", "backend/tests/audit", "-q"],
]
```

Always run `git diff --check`. Run npm commands with cwd `frontend`; run Python commands at repo root. If a script such as `test:run` is not present on a branch that did not change frontend quality, skip that command with an explicit informational result rather than failing unrelated branches.

- [ ] **Step 4: Implement hook stdin/stdout**

Read the Codex event JSON from stdin. On success print `{"continue": true}`. On failure print `{"decision":"block","reason":"..."}`. Add `--repo PATH` for explicit main-review invocation.

- [ ] **Step 5: Verify and commit**

```powershell
conda run -n myself python -m pytest backend/tests/audit/test_audit_gate.py -q
git add .codex/hooks backend/tests/audit
git commit -m "feat(audit): add deterministic branch gate"
```

### Task 2: Configure project-local Stop hooks

**Files:**
- Create: `.codex/hooks.json`
- Modify: `backend/tests/audit/test_audit_gate.py`

**Interfaces:**
- Consumes: `.codex/hooks/audit_gate.py`.
- Produces: matching `SubagentStop` and `Stop` command hooks.

- [ ] **Step 1: Add a configuration test**

Load `.codex/hooks.json` and assert both keys exist, each has one command handler, timeout is at least 180 seconds, and Windows uses `conda run -n myself python`.

- [ ] **Step 2: Create hooks.json**

Configure both events with generic `python3` command and a `commandWindows` override. Resolve the hook path through `git rev-parse --show-toplevel`; do not assume the session starts at repo root.

- [ ] **Step 3: Verify success and failure paths**

Run the audit tests, then invoke the CLI on the clean audit branch and with a test-only injected failing command. Confirm success returns `continue: true` and failure returns `decision: block` without editing files.

- [ ] **Step 4: Commit**

```powershell
git add .codex/hooks.json backend/tests/audit/test_audit_gate.py
git commit -m "chore(audit): enforce codex stop review"
```

### Task 3: Document trust, manual fallback, and lifecycle

**Files:**
- Create: `docs/audit-workflow.md`
- Modify: `docs/DEVLOG.md`

- [ ] **Step 1: Write the operator guide**

Document:

- project Hook trust review through `/hooks`;
- current-session hot-load limitations;
- manual command `conda run -n myself python .codex/hooks/audit_gate.py --repo <worktree>`;
- Hook does not replace main diff review;
- heartbeat is read-only and must stop after worktree cleanup.

- [ ] **Step 2: Add the DEVLOG entry**

Use the required 2026-07-11 five-field template and explain Hook, heartbeat, and human merge authority.

- [ ] **Step 3: Run the complete audit gate**

```powershell
conda run -n myself python -m pytest backend/tests/audit/test_audit_gate.py -q
conda run -n myself python .codex/hooks/audit_gate.py --repo .
git diff --check main...HEAD
```

Expected: all commands exit 0 and the script makes no repository changes.

- [ ] **Step 4: Commit and hand off**

```powershell
git add docs/audit-workflow.md docs/DEVLOG.md
git commit -m "docs(audit): explain automated review workflow"
git status --short
```

Expected: clean worktree. Report commits, audit test count, and manual audit output to the main agent.

