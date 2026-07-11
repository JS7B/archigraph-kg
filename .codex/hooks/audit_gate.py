from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


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
    return any(path == item or path.startswith(item) for item in allowed)


def audit_repository(
    repo: Path,
    *,
    base: str = "main",
    run_command: Callable[
        [list[str], Path], subprocess.CompletedProcess[str]
    ] = _default_command_runner,
) -> AuditReport:
    repo = repo.resolve()
    branch = _current_branch(repo)
    paths = changed_paths(repo, base)
    report = AuditReport(branch=branch)

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout:
        report.failures.append("worktree has uncommitted changes")

    for args in (
        ("diff", "--check", f"{base}...HEAD", "--"),
        ("diff", "--check", "--"),
        ("diff", "--cached", "--check", "--"),
    ):
        failure = _run_git_check(repo, *args)
        if failure:
            report.failures.append(failure)

    allowed = BRANCH_SCOPES.get(branch)
    if allowed:
        out_of_scope = [path for path in paths if not _is_allowed(path, allowed)]
        if out_of_scope:
            report.failures.append(
                f"paths outside {branch} scope: {', '.join(out_of_scope)}"
            )

    for command in commands_for_paths(paths):
        cwd = repo / "frontend" if command[0] == "npm" else repo
        if command[:2] == ["npm", "run"] and branch != "feat/frontend-quality":
            script = command[2]
            if not _npm_script_exists(repo, script):
                report.information.append(
                    f"Skipped npm run {script}: script is absent and branch is not feat/frontend-quality"
                )
                continue
        result = run_command(command, cwd)
        if result.returncode != 0:
            detail = (result.stdout + result.stderr).strip()
            report.failures.append(
                f"{' '.join(command)} failed in {cwd}: {detail[-2000:]}"
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
    return commands


def hook_decision(
    branch: str, stop_hook_active: bool, failures: list[str]
) -> dict[str, object]:
    if branch == "main" or stop_hook_active or not failures:
        return {"continue": True}
    if branch.startswith("feat/"):
        return {"decision": "block", "reason": "\n".join(failures)}
    return {"continue": True}


def _read_event() -> dict[str, object]:
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the read-only branch audit gate.")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    event = _read_event()
    branch = _current_branch(args.repo)
    stop_hook_active = event.get("stop_hook_active") is True

    if branch == "main" or not branch.startswith("feat/") or stop_hook_active:
        decision = {"continue": True}
    else:
        report = audit_repository(args.repo)
        for item in report.information:
            print(item, file=sys.stderr)
        decision = hook_decision(branch, False, report.failures)
    print(json.dumps(decision, ensure_ascii=False))


if __name__ == "__main__":
    main()
