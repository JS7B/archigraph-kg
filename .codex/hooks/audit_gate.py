from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


def npm_executable(platform: str | None = None) -> str:
    platform = sys.platform if platform is None else platform
    return "npm.cmd" if platform == "win32" else "npm"


NPM_EXECUTABLE = npm_executable()
FRONTEND_COMMANDS = [
    [NPM_EXECUTABLE, "run", "lint"],
    [NPM_EXECUTABLE, "run", "typecheck"],
    [NPM_EXECUTABLE, "run", "test:run"],
    [NPM_EXECUTABLE, "run", "build"],
]
EVAL_COMMANDS = [
    [sys.executable, "-m", "pytest", "evals/tests", "-q"],
]
AUDIT_COMMANDS = [
    [
        sys.executable,
        "-m",
        "pytest",
        "backend/tests/audit",
        "-q",
        "--confcutdir=backend/tests/audit",
    ],
]
PYTHON_PARSING_COMMAND = [
    sys.executable,
    "-m",
    "pytest",
    "backend/tests/parsing",
    "-q",
]
PYTHON_EXTRACTION_COMMAND = [
    sys.executable,
    "-m",
    "pytest",
    "backend/tests/extraction",
    "-q",
]
PYTHON_GRAPH_COMMAND = [
    sys.executable,
    "-m",
    "pytest",
    "backend/tests/graph",
    "backend/tests/routers/test_graph.py",
    "-q",
]

BRANCH_SCOPES = {
    "feat/frontend-quality": ("frontend/",),
    "feat/evaluation-quality": ("evals/", "docs/evaluation.md"),
    "feat/audit-infrastructure": (
        ".codex/",
        "backend/tests/audit/",
        "docs/audit-workflow.md",
        "docs/DEVLOG.md",
    ),
    "feat/kg-parsing": (
        "backend/app/parsing/",
        "backend/tests/parsing/",
        "backend/DEVLOG.md",
    ),
    "feat/kg-extraction": (
        "backend/app/extraction/",
        "backend/tests/extraction/",
        "backend/DEVLOG.md",
    ),
    "feat/kg-resolution": (
        "backend/app/resolution/",
        "backend/tests/resolution/",
        "backend/DEVLOG.md",
    ),
    "feat/kg-community-api": (
        "backend/app/graph/",
        "backend/app/routers/graph.py",
        "backend/tests/graph/",
        "backend/tests/routers/test_graph.py",
        "backend/DEVLOG.md",
    ),
    "feat/graph-experience": (
        "frontend/",
        "frontend/DEVLOG.md",
    ),
}


@dataclass
class AuditReport:
    branch: str
    failures: list[str] = field(default_factory=list)
    information: list[str] = field(default_factory=list)


def _git_paths(repo: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def changed_paths(repo: Path, base: str = "main") -> list[str]:
    candidates = [
        *_git_paths(repo, "diff", "--name-only", f"{base}...HEAD", "--"),
        *_git_paths(repo, "diff", "--name-only", "--"),
        *_git_paths(repo, "diff", "--cached", "--name-only", "--"),
    ]
    return list(dict.fromkeys(candidates))


def _current_branch(repo: Path) -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _run_git_check(repo: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return None
    detail = (result.stdout + result.stderr).strip()
    return f"git {' '.join(args)} failed: {detail}"


def _default_command_runner(
    command: list[str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _npm_script_exists(repo: Path, script: str) -> bool:
    package_json = repo / "frontend" / "package.json"
    if not package_json.is_file():
        return False
    data = json.loads(package_json.read_text(encoding="utf-8"))
    return script in data.get("scripts", {})


def _is_allowed(path: str, allowed: tuple[str, ...]) -> bool:
    return any(
        path.startswith(item) if item.endswith("/") else path == item
        for item in allowed
    )


def _exception_failure(context: str, error: Exception) -> str:
    detail = str(error).strip()
    suffix = f": {detail}" if detail else ""
    return f"{context}: {type(error).__name__}{suffix}"


def audit_repository(
    repo: Path,
    *,
    base: str = "main",
    run_command: Callable[
        [list[str], Path], subprocess.CompletedProcess[str]
    ] = _default_command_runner,
) -> AuditReport:
    report = AuditReport(branch="")
    try:
        repo = repo.resolve()
        report.branch = _current_branch(repo)
        paths = changed_paths(repo, base)
    except Exception as error:
        report.failures.append(_exception_failure("audit setup failed", error))
        return report

    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        if status.stdout:
            report.failures.append("worktree has uncommitted changes")
    except Exception as error:
        report.failures.append(_exception_failure("git status failed", error))

    for args in (
        ("diff", "--check", f"{base}...HEAD", "--"),
        ("diff", "--check", "--"),
        ("diff", "--cached", "--check", "--"),
    ):
        try:
            failure = _run_git_check(repo, *args)
            if failure:
                report.failures.append(failure)
        except Exception as error:
            report.failures.append(
                _exception_failure(f"git {' '.join(args)} failed", error)
            )

    allowed = BRANCH_SCOPES.get(report.branch)
    if allowed:
        out_of_scope = [path for path in paths if not _is_allowed(path, allowed)]
        if out_of_scope:
            report.failures.append(
                f"paths outside {report.branch} scope: {', '.join(out_of_scope)}"
            )

    for command in commands_for_paths(paths):
        cwd = repo / "frontend" if command[0] == NPM_EXECUTABLE else repo
        try:
            if (
                command[:2] == [NPM_EXECUTABLE, "run"]
                and report.branch != "feat/frontend-quality"
            ):
                script = command[2]
                if not _npm_script_exists(repo, script):
                    report.information.append(
                        f"Skipped npm run {script}: script is absent and branch is not feat/frontend-quality"
                    )
                    continue
            result = run_command(command, cwd)
            if result.returncode == 0:
                continue
            detail = ((result.stdout or "") + (result.stderr or "")).strip()
            report.failures.append(
                f"{' '.join(command)} failed in {cwd}: {detail[-2000:]}"
            )
        except Exception as error:
            report.failures.append(
                _exception_failure(f"{' '.join(command)} failed in {cwd}", error)
            )

    return report


def commands_for_paths(paths: list[str]) -> list[list[str]]:
    commands: list[list[str]] = []
    if any(path.startswith("frontend/") for path in paths):
        commands.extend(FRONTEND_COMMANDS)
    if any(path.startswith("evals/") or path == "docs/evaluation.md" for path in paths):
        commands.extend(EVAL_COMMANDS)
    if any(path.startswith(".codex/") or path.startswith("backend/tests/audit/") for path in paths):
        commands.extend(AUDIT_COMMANDS)
    if any(
        path.startswith("backend/app/parsing/")
        or path.startswith("backend/tests/parsing/")
        for path in paths
    ):
        commands.append(PYTHON_PARSING_COMMAND)
    if any(
        path.startswith("backend/app/extraction/")
        or path.startswith("backend/tests/extraction/")
        for path in paths
    ):
        commands.append(PYTHON_EXTRACTION_COMMAND)
    if any(
        path.startswith("backend/app/graph/")
        or path.startswith("backend/tests/graph/")
        or path == "backend/app/routers/graph.py"
        or path == "backend/tests/routers/test_graph.py"
        for path in paths
    ):
        commands.append(PYTHON_GRAPH_COMMAND)
    return commands


def hook_decision(
    branch: str, stop_hook_active: bool, failures: list[str]
) -> dict[str, object]:
    if branch == "main" or stop_hook_active or not failures:
        return {"continue": True}
    if branch.startswith("feat/"):
        return {"decision": "block", "reason": "\n".join(failures)}
    return {"continue": True}


def render_decision(decision: dict[str, object]) -> str:
    return json.dumps(decision)


def _blocked_by_exception(context: str, error: Exception) -> dict[str, object]:
    return {"decision": "block", "reason": _exception_failure(context, error)}


def _read_event() -> dict[str, object]:
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the read-only branch audit gate.")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        event = _read_event()
        if not isinstance(event, dict):
            raise ValueError("hook input must be a JSON object")
        stop_hook_active = event.get("stop_hook_active") is True
    except Exception as error:
        decision = _blocked_by_exception("invalid hook input", error)
        print(render_decision(decision))
        return

    if stop_hook_active:
        print(render_decision({"continue": True}))
        return

    try:
        branch = _current_branch(args.repo)
        if branch == "main" or not branch.startswith("feat/"):
            decision = {"continue": True}
        else:
            report = audit_repository(args.repo)
            for item in report.information:
                print(item, file=sys.stderr)
            decision = hook_decision(branch, False, report.failures)
    except Exception as error:
        decision = _blocked_by_exception("audit gate failed", error)
    print(render_decision(decision))


if __name__ == "__main__":
    main()
