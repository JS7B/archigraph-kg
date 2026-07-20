from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / ".codex" / "hooks"))

from audit_gate import (  # noqa: E402
    _is_allowed,
    audit_repository,
    changed_paths,
    commands_for_paths,
    hook_decision,
    npm_executable,
    render_decision,
)


def commit_path(repo: Path, relative_path: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("change\n", encoding="utf-8")
    run_git(repo, "add", relative_path)
    run_git(repo, "commit", "-m", f"change {relative_path}")


def run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def init_repo(repo: Path) -> None:
    repo.mkdir()
    run_git(repo, "init", "-b", "main")
    run_git(repo, "config", "user.name", "Audit Test")
    run_git(repo, "config", "user.email", "audit@example.invalid")
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    run_git(repo, "add", "tracked.txt")
    run_git(repo, "commit", "-m", "base")


def test_frontend_paths_select_all_frontend_gates():
    commands = commands_for_paths(["frontend/src/App.tsx"])
    rendered = [" ".join(command) for command in commands]
    npm = npm_executable()

    assert any(f"{npm} run lint" in command for command in rendered)
    assert any(f"{npm} run typecheck" in command for command in rendered)
    assert any(f"{npm} run test:run" in command for command in rendered)
    assert any(f"{npm} run build" in command for command in rendered)


def test_parsing_paths_select_targeted_backend_gate():
    assert commands_for_paths(["backend/app/parsing/models.py"]) == [
        [
            sys.executable,
            "-m",
            "pytest",
            "backend/tests/parsing",
            "-q",
            "--confcutdir=backend/tests/parsing",
        ]
    ]


def test_extraction_paths_select_targeted_backend_gate():
    assert commands_for_paths(["backend/app/extraction/models.py"]) == [
        [
            sys.executable,
            "-m",
            "pytest",
            "backend/tests/extraction",
            "-q",
            "--confcutdir=backend/tests/extraction",
            "--ignore=backend/tests/extraction/test_writer.py",
            "--ignore=backend/tests/extraction/test_llm_real.py",
        ]
    ]


def test_run_task_paths_select_targeted_backend_gate():
    expected = [
        sys.executable,
        "-m",
        "pytest",
        "tests/runs/test_tasks.py",
        "-q",
        "--confcutdir=tests/runs",
        "-k",
        "not reads_history_and_writes_back",
    ]

    assert commands_for_paths(["backend/app/runs/tasks.py"]) == [expected]
    assert commands_for_paths(["backend/tests/runs/test_tasks.py"]) == [expected]


def test_run_task_gate_runs_from_backend_directory(tmp_path):
    expected = [
        sys.executable,
        "-m",
        "pytest",
        "tests/runs/test_tasks.py",
        "-q",
        "--confcutdir=tests/runs",
        "-k",
        "not reads_history_and_writes_back",
    ]
    repo = tmp_path / "repo"
    init_repo(repo)
    run_git(repo, "switch", "-c", "feat/kg-extraction")
    commit_path(repo, "backend/app/runs/tasks.py")
    calls: list[tuple[list[str], Path]] = []

    def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append((command, cwd))
        return subprocess.CompletedProcess(command, 0, "passed", "")

    report = audit_repository(repo, run_command=run_command)

    assert report.failures == []
    assert calls == [(expected, repo / "backend")]


def test_resolution_paths_select_targeted_backend_gate():
    expected = [
        sys.executable,
        "-m",
        "pytest",
        "tests/resolution",
        "-q",
        "--confcutdir=tests/resolution",
    ]

    assert commands_for_paths(["backend/app/resolution/resolver.py"]) == [expected]
    assert commands_for_paths(["backend/tests/resolution/test_resolver.py"]) == [
        expected
    ]


def test_resolution_branch_routes_schema_changes_to_resolution_gate():
    expected = [
        sys.executable,
        "-m",
        "pytest",
        "tests/resolution",
        "-q",
        "--confcutdir=tests/resolution",
    ]

    assert commands_for_paths(
        ["backend/app/graph/schema.py"], branch="feat/kg-resolution"
    ) == [expected]
    assert commands_for_paths(
        [
            "backend/app/resolution/persistence.py",
            "backend/app/graph/schema.py",
        ],
        branch="feat/kg-resolution",
    ) == [expected]


def test_resolution_gate_runs_from_backend_directory(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    run_git(repo, "switch", "-c", "feat/kg-resolution")
    commit_path(repo, "backend/app/resolution/resolver.py")
    calls: list[tuple[list[str], Path]] = []

    def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append((command, cwd))
        return subprocess.CompletedProcess(command, 0, "passed", "")

    report = audit_repository(repo, run_command=run_command)

    assert report.failures == []
    assert calls == [
        (
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/resolution",
                "-q",
                "--confcutdir=tests/resolution",
            ],
            repo / "backend",
        )
    ]


def test_graph_and_graph_router_paths_select_targeted_backend_gate():
    expected = [
        sys.executable,
        "-m",
        "pytest",
        "backend/tests/graph",
        "backend/tests/routers/test_graph.py",
        "-q",
    ]

    assert commands_for_paths(["backend/app/graph/search.py"]) == [expected]
    assert commands_for_paths(["backend/app/routers/graph.py"]) == [expected]


def test_targeted_backend_gates_are_deduplicated_for_mixed_paths():
    commands = commands_for_paths(
        [
            "backend/app/parsing/models.py",
            "backend/tests/parsing/test_models.py",
            "backend/app/extraction/models.py",
            "backend/tests/extraction/test_models.py",
            "backend/app/graph/search.py",
            "backend/app/routers/graph.py",
        ]
    )

    assert commands == [
        [
            sys.executable,
            "-m",
            "pytest",
            "backend/tests/parsing",
            "-q",
            "--confcutdir=backend/tests/parsing",
        ],
        [
            sys.executable,
            "-m",
            "pytest",
            "backend/tests/extraction",
            "-q",
            "--confcutdir=backend/tests/extraction",
            "--ignore=backend/tests/extraction/test_writer.py",
            "--ignore=backend/tests/extraction/test_llm_real.py",
        ],
        [
            sys.executable,
            "-m",
            "pytest",
            "backend/tests/graph",
            "backend/tests/routers/test_graph.py",
            "-q",
        ],
    ]


def test_new_quality_worktree_scopes_block_paths_outside_their_ownership(tmp_path):
    cases = [
        (
            "feat/kg-parsing",
            "backend/app/parsing/models.py",
            "backend/app/extraction/models.py",
        ),
        (
            "feat/kg-extraction",
            "backend/app/runs/tasks.py",
            "backend/app/parsing/models.py",
        ),
        (
            "feat/kg-evaluation",
            "evals/metrics.py",
            "backend/app/extraction/models.py",
        ),
        (
            "feat/kg-resolution",
            "backend/app/graph/schema.py",
            "backend/app/graph/search.py",
        ),
        (
            "feat/kg-community-api",
            "backend/app/routers/graph.py",
            "backend/app/parsing/models.py",
        ),
        (
            "feat/graph-experience",
            "frontend/src/views/GraphView/GraphView.tsx",
            "backend/app/routers/graph.py",
        ),
    ]

    for branch, allowed_path, forbidden_path in cases:
        repo = tmp_path / branch.replace("/", "-")
        init_repo(repo)
        run_git(repo, "switch", "-c", branch)
        commit_path(repo, allowed_path)
        report = audit_repository(repo)
        assert not any("outside" in item for item in report.failures)

        commit_path(repo, forbidden_path)
        report = audit_repository(repo)
        assert any(f"outside {branch} scope" in item for item in report.failures)


def test_agentic_rag_worktree_scopes_accept_owned_paths_and_reject_unrelated_paths(
    tmp_path,
):
    cases = [
        (
            "feat/qa-memory-grounding",
            [
                "backend/app/qa/question_rewrite.py",
                "backend/tests/qa/test_memory_grounding.py",
            ],
            "backend/app/conversations/store.py",
        ),
        (
            "feat/qa-citation-guard",
            [
                "backend/app/qa/finalize.py",
                "backend/tests/qa/test_answer_finalizer.py",
            ],
            "backend/app/runs/tasks.py",
        ),
        (
            "feat/conversation-atomic-turn",
            [
                "backend/app/conversations/store.py",
                "backend/tests/conversations/test_atomic_turn.py",
            ],
            "backend/app/qa/agent.py",
        ),
        (
            "feat/qa-canonical-expand",
            [
                "backend/app/qa/expand.py",
                "backend/tests/qa/test_canonical_expand.py",
            ],
            "backend/app/conversations/store.py",
        ),
    ]

    def pass_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, "passed", "")

    for branch, allowed_paths, forbidden_path in cases:
        repo = tmp_path / branch.replace("/", "-")
        init_repo(repo)
        run_git(repo, "switch", "-c", branch)
        for allowed_path in allowed_paths:
            commit_path(repo, allowed_path)
        report = audit_repository(repo, run_command=pass_command)
        assert not any("outside" in item for item in report.failures)

        commit_path(repo, forbidden_path)
        report = audit_repository(repo, run_command=pass_command)
        assert any(f"outside {branch} scope" in item for item in report.failures)


def test_agentic_rag_branches_select_compile_and_focused_deterministic_gates():
    cases = {
        "feat/qa-memory-grounding": {
            "path": "backend/app/runs/tasks.py",
            "pytest_targets": [
                "tests/qa/test_memory_grounding.py",
                "tests/runs/test_tasks.py",
            ],
        },
        "feat/qa-citation-guard": {
            "path": "backend/app/qa/finalize.py",
            "pytest_targets": [
                "tests/qa/test_answer_finalizer.py",
                "tests/qa/test_pipeline.py",
            ],
        },
        "feat/conversation-atomic-turn": {
            "path": "backend/app/conversations/store.py",
            "pytest_targets": [
                "tests/conversations/test_atomic_turn.py",
                "tests/qa/test_chat_contract.py",
                "tests/runs/test_tasks.py",
            ],
        },
        "feat/qa-canonical-expand": {
            "path": "backend/app/qa/expand.py",
            "pytest_targets": ["tests/qa/test_canonical_expand.py"],
        },
    }

    for branch, case in cases.items():
        commands = commands_for_paths([case["path"]], branch=branch)
        rendered = [" ".join(command) for command in commands]

        assert " -m compileall " in f" {rendered[0]} "
        assert sum(" -m compileall " in f" {command} " for command in rendered) == 1
        for target in case["pytest_targets"]:
            assert sum(target in command for command in rendered) == 1
        assert all("test_agent.py" not in command for command in rendered)


def test_agentic_rag_branch_gates_run_from_backend_directory(tmp_path):
    cases = {
        "feat/qa-memory-grounding": "backend/app/qa/agent.py",
        "feat/qa-citation-guard": "backend/app/qa/finalize.py",
        "feat/conversation-atomic-turn": "backend/app/conversations/store.py",
        "feat/qa-canonical-expand": "backend/app/qa/expand.py",
    }

    for branch, changed_path in cases.items():
        repo = tmp_path / branch.replace("/", "-")
        init_repo(repo)
        run_git(repo, "switch", "-c", branch)
        commit_path(repo, changed_path)
        calls: list[tuple[list[str], Path]] = []

        def run_command(
            command: list[str], cwd: Path
        ) -> subprocess.CompletedProcess[str]:
            calls.append((command, cwd))
            return subprocess.CompletedProcess(command, 0, "passed", "")

        report = audit_repository(repo, run_command=run_command)

        assert report.failures == []
        assert calls
        assert all(cwd == repo / "backend" for _, cwd in calls)


def test_npm_launcher_uses_cmd_only_on_windows():
    assert npm_executable("win32") == "npm.cmd"
    assert npm_executable("linux") == "npm"


def test_active_stop_hook_never_blocks_again():
    assert hook_decision("feat/audit", True, ["failed"])["continue"] is True


def test_failed_feature_audit_requests_continuation():
    result = hook_decision("feat/audit", False, ["pytest failed"])

    assert result["decision"] == "block"
    assert "pytest failed" in result["reason"]


def test_changed_paths_combines_committed_unstaged_and_cached_changes(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    run_git(repo, "switch", "-c", "feat/test")
    (repo / "committed.txt").write_text("committed\n", encoding="utf-8")
    run_git(repo, "add", "committed.txt")
    run_git(repo, "commit", "-m", "feature")

    (repo / "tracked.txt").write_text("unstaged\n", encoding="utf-8")
    (repo / "staged.txt").write_text("staged\n", encoding="utf-8")
    run_git(repo, "add", "staged.txt")

    assert changed_paths(repo) == ["committed.txt", "tracked.txt", "staged.txt"]


def test_policy_selects_each_non_frontend_gate_once():
    commands = commands_for_paths(
        [
            "evals/run_eval.py",
            "docs/evaluation.md",
            ".codex/hooks/audit_gate.py",
            "backend/tests/audit/test_audit_gate.py",
        ]
    )
    rendered = [" ".join(command) for command in commands]

    assert sum("pytest evals/tests" in command for command in rendered) == 1
    assert sum("pytest backend/tests/audit" in command for command in rendered) == 1


def test_python_gates_reuse_the_hook_interpreter():
    commands = commands_for_paths(
        ["evals/run_eval.py", ".codex/hooks/audit_gate.py"]
    )

    assert all(command[:3] == [sys.executable, "-m", "pytest"] for command in commands)


def test_audit_repository_runs_audit_tests_from_repo_root(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    run_git(repo, "switch", "-c", "feat/audit-infrastructure")
    hook = repo / ".codex" / "hooks" / "audit_gate.py"
    hook.parent.mkdir(parents=True)
    hook.write_text("# audit\n", encoding="utf-8")
    run_git(repo, "add", ".codex/hooks/audit_gate.py")
    run_git(repo, "commit", "-m", "audit")
    calls: list[tuple[list[str], Path]] = []

    def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append((command, cwd))
        return subprocess.CompletedProcess(command, 0, "passed", "")

    report = audit_repository(repo, run_command=run_command)

    assert report.failures == []
    assert calls == [
        (
            [
                sys.executable,
                "-m",
                "pytest",
                "backend/tests/audit",
                "-q",
                "--confcutdir=backend/tests/audit",
            ],
            repo,
        )
    ]


def test_audit_branch_rejects_paths_outside_its_owned_scope(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    run_git(repo, "switch", "-c", "feat/audit-infrastructure")
    frontend_file = repo / "frontend" / "src" / "App.tsx"
    frontend_file.parent.mkdir(parents=True)
    frontend_file.write_text("export {};\n", encoding="utf-8")
    run_git(repo, "add", "frontend/src/App.tsx")
    run_git(repo, "commit", "-m", "wrong scope")

    report = audit_repository(repo)

    assert any("outside feat/audit-infrastructure scope" in item for item in report.failures)


def test_scope_file_entries_require_exact_match():
    allowed = ("evals/", "docs/evaluation.md")

    assert _is_allowed("docs/evaluation.md", allowed)
    assert not _is_allowed("docs/evaluation.md.bak", allowed)
    assert not _is_allowed("docs/evaluation.md/child", allowed)
    assert _is_allowed("evals/tests/test_metrics.py", allowed)


def test_missing_frontend_package_scripts_are_informational_off_quality_branch(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    run_git(repo, "switch", "-c", "feat/other")
    frontend_file = repo / "frontend" / "README.md"
    frontend_file.parent.mkdir()
    frontend_file.write_text("docs\n", encoding="utf-8")
    run_git(repo, "add", "frontend/README.md")
    run_git(repo, "commit", "-m", "frontend docs")

    report = audit_repository(repo)

    assert report.failures == []
    assert any("Skipped npm run lint" in item for item in report.information)
    assert any("Skipped npm run test:run" in item for item in report.information)


def test_bad_base_is_reported_without_raising(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    run_git(repo, "switch", "-c", "feat/other")

    report = audit_repository(repo, base="missing-audit-base")

    assert any("missing-audit-base" in item for item in report.failures)


def test_missing_npm_is_recorded_as_audit_failure(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    run_git(repo, "switch", "-c", "feat/frontend-quality")
    frontend_file = repo / "frontend" / "src" / "App.tsx"
    frontend_file.parent.mkdir(parents=True)
    frontend_file.write_text("export {};\n", encoding="utf-8")
    run_git(repo, "add", "frontend/src/App.tsx")
    run_git(repo, "commit", "-m", "frontend")

    def missing_npm(
        command: list[str], cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("npm is missing")

    report = audit_repository(repo, run_command=missing_npm)

    assert any(
        f"{npm_executable()} run lint" in item and "npm is missing" in item
        for item in report.failures
    )


def test_unexpected_executor_exception_is_recorded_as_audit_failure(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    run_git(repo, "switch", "-c", "feat/audit-infrastructure")
    hook = repo / ".codex" / "hooks" / "audit_gate.py"
    hook.parent.mkdir(parents=True)
    hook.write_text("# audit\n", encoding="utf-8")
    run_git(repo, "add", ".codex/hooks/audit_gate.py")
    run_git(repo, "commit", "-m", "audit")

    def broken_runner(
        command: list[str], cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        raise RuntimeError("runner exploded")

    report = audit_repository(repo, run_command=broken_runner)

    assert any("runner exploded" in item for item in report.failures)


def test_cli_returns_continue_for_clean_feature_repo(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    run_git(repo, "switch", "-c", "feat/other")

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / ".codex" / "hooks" / "audit_gate.py"), "--repo", str(repo)],
        input="{}",
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(result.stdout) == {"continue": True}


def test_cli_bad_json_fails_closed_with_ascii_decision(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    run_git(repo, "switch", "-c", "feat/other")

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / ".codex" / "hooks" / "audit_gate.py"), "--repo", str(repo)],
        input="{",
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["decision"] == "block"
    assert "invalid hook input" in payload["reason"]
    assert result.stdout.isascii()


def test_cli_missing_repo_fails_closed_with_ascii_decision(tmp_path):
    missing_repo = tmp_path / "missing"

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / ".codex" / "hooks" / "audit_gate.py"), "--repo", str(missing_repo)],
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["decision"] == "block"
    assert "audit gate failed" in payload["reason"]
    assert result.stdout.isascii()


def test_active_stop_hook_bypasses_missing_repo_after_valid_json(tmp_path):
    missing_repo = tmp_path / "missing"

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / ".codex" / "hooks" / "audit_gate.py"), "--repo", str(missing_repo)],
        input=json.dumps({"stop_hook_active": True}),
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(result.stdout) == {"continue": True}


def test_cli_blocks_once_for_failed_feature_repo(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    run_git(repo, "switch", "-c", "feat/other")
    (repo / "tracked.txt").write_text("trailing whitespace   \n", encoding="utf-8")
    command = [
        sys.executable,
        str(REPO_ROOT / ".codex" / "hooks" / "audit_gate.py"),
        "--repo",
        str(repo),
    ]

    blocked = subprocess.run(
        command,
        input="{}",
        capture_output=True,
        text=True,
        check=True,
    )
    allowed = subprocess.run(
        command,
        input=json.dumps({"stop_hook_active": True}),
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(blocked.stdout)["decision"] == "block"
    assert json.loads(allowed.stdout) == {"continue": True}


def test_non_ascii_failure_reason_is_ascii_safe_and_round_trips():
    decision = hook_decision("feat/audit", False, ["中文失败"])

    output = render_decision(decision)

    assert output.isascii()
    assert json.loads(output) == decision


def test_stop_hooks_use_one_cross_platform_command_handler_each():
    config = json.loads((REPO_ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))

    assert set(config["hooks"]) == {"Stop", "SubagentStop"}
    for event in ("Stop", "SubagentStop"):
        groups = config["hooks"][event]
        assert len(groups) == 1
        handlers = groups[0]["hooks"]
        assert len(handlers) == 1
        handler = handlers[0]
        assert handler["type"] == "command"
        assert handler["timeout"] >= 180
        assert "python3" in handler["command"]
        assert "git rev-parse --show-toplevel" in handler["command"]
        assert "conda run -n myself python" in handler["commandWindows"]
        assert "git rev-parse --show-toplevel" in handler["commandWindows"]
