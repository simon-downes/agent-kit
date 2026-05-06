"""Brain git operations — commit, status."""

import subprocess
from pathlib import Path


def git_status(repo_path: Path) -> dict:
    """Get git status for a directory."""
    result: dict = {}

    git_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if git_result.returncode == 0:
        changes = [line for line in git_result.stdout.strip().splitlines() if line]
        result["changes"] = changes
    else:
        result["changes"] = []
        result["git_error"] = "not a git repository"

    return result


def commit(context_path: Path, message: str, paths: list[str] | None = None) -> str | None:
    """Stage and commit. Returns commit hash or None."""
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=context_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if not status.stdout.strip():
        return None

    add_cmd = ["git", "add"] + (paths if paths else ["-A"])
    result = subprocess.run(
        add_cmd,
        cwd=context_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"git add failed: {result.stderr.strip()}")

    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=context_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"git commit failed: {result.stderr.strip()}")

    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=context_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()
