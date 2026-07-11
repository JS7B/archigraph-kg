from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / ".codex" / "hooks"))

from audit_gate import (  # noqa: E402
    audit_repository,
    changed_paths,
    commands_for_paths,
    hook_decision,
)


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
                "conda",
                "run",
                "-n",
                "myself",
                "python",
                "-m",
                "pytest",
                "backend/tests/audit",
                "-q",
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
