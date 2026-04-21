"""Brain git operations — init, clone, commit, status."""

import subprocess
from pathlib import Path

from agent_kit.brain.client import ENTITY_DIRS, GITIGNORE_CONTENT


def init_local(context_path: Path) -> str:
    """Create a local context with standard directories and git init."""
    for subdir in ENTITY_DIRS:
        (context_path / subdir).mkdir(parents=True, exist_ok=True)

    (context_path / ".gitignore").write_text(GITIGNORE_CONTENT)

    result = subprocess.run(["git", "init"], cwd=context_path, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"git init failed for {context_path.name}: {result.stderr.strip()}")

    return f"created {context_path.name}"


def clone_repo(context_path: Path, repo: str) -> str:
    """Clone a remote repo into a context directory."""
    result = subprocess.run(
        ["git", "clone", repo, str(context_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"git clone failed for {context_path.name}: {result.stderr.strip()}")
    return f"cloned {context_path.name} from {repo}"


def context_status(context_path: Path) -> dict:
    """Get git status for a context."""
    result: dict = {"context": context_path.name}

    git_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=context_path,
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
    """Stage and commit in a context. Returns commit hash or None."""
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
        raise ValueError(f"git add failed in {context_path.name}: {result.stderr.strip()}")

    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=context_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"git commit failed in {context_path.name}: {result.stderr.strip()}")

    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=context_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def get_remote_url(context_path: Path) -> str | None:
    """Get the origin remote URL, or None if not set."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=context_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None
