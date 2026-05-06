"""Project resolution — detect current project from working directory and git remote."""

import subprocess
from fnmatch import fnmatch
from pathlib import Path

import click
import yaml

from agent_kit.config import load_config
from agent_kit.errors import handle_errors, output

PROJECTS_PATH = Path("~/.agent-kit/projects.yaml").expanduser()


def _parse_remote(url: str) -> tuple[str, str]:
    """Extract org and repo from a git remote URL.

    Supports SSH (git@host:org/repo.git) and HTTPS (https://host/org/repo.git).
    """
    url = url.strip().rstrip("/").removesuffix(".git")
    if ":" in url and not url.startswith("http"):
        # SSH: git@github.com:org/repo
        path = url.split(":", 1)[1]
    else:
        # HTTPS: https://github.com/org/repo
        path = "/".join(url.split("/")[-2:])

    parts = path.split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "", parts[-1] if parts else ""


def _get_remote() -> str | None:
    """Get the origin remote URL, or None."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def resolve_project(config: dict) -> dict:
    """Resolve the current project: name, org, path, source, issues, slack."""
    cwd = Path.cwd().resolve()
    project_dir = Path(config.get("project_dir", "~/dev")).expanduser().resolve()

    # Determine local project name from project_dir
    name = None
    try:
        relative = cwd.relative_to(project_dir)
        if relative.parts:
            name = relative.parts[0]
    except ValueError:
        pass

    if not name:
        name = cwd.name

    path = str(project_dir / name) if name and project_dir.exists() else str(cwd)

    # Determine org and source from git remote
    remote = _get_remote()
    if remote:
        org, remote_repo = _parse_remote(remote)
        source = remote
    else:
        org = None
        remote_repo = None
        source = "local"

    # Resolve config from projects.yaml
    projects_config = _load_projects_config()
    resolved = _resolve_project_config(org, remote_repo, projects_config)

    return {
        "name": name,
        "org": org or None,
        "path": path,
        "source": source,
        "issues": resolved.get("issues"),
        "slack": resolved.get("slack"),
    }


def _load_projects_config() -> dict:
    """Load ~/.agent-kit/projects.yaml, returning empty dict if missing."""
    if not PROJECTS_PATH.exists():
        return {}
    try:
        return yaml.safe_load(PROJECTS_PATH.read_text()) or {}
    except Exception:
        return {}


def _resolve_project_config(org: str | None, repo: str | None, config: dict) -> dict:
    """Resolve project config with hierarchical merge: defaults → org → glob → exact."""
    result = dict(config.get("defaults") or {})

    if not org:
        return result

    # Org-level
    org_config = config.get(org)
    if isinstance(org_config, dict):
        result = {**result, **org_config}

    # Glob patterns: <org>/<pattern>
    if repo:
        for key, value in config.items():
            if "/" in key and "*" in key and isinstance(value, dict):
                pattern_org, pattern_name = key.split("/", 1)
                if pattern_org == org and fnmatch(repo, pattern_name):
                    result = {**result, **value}

        # Exact match
        exact = config.get(f"{org}/{repo}")
        if isinstance(exact, dict):
            result = {**result, **exact}

    return result


@click.command()
@handle_errors
def project() -> None:
    """Detect the current project and resolve its configuration."""
    config = load_config()
    output(resolve_project(config))
