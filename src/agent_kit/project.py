"""Project resolution — detect current project from working directory, git remote, or cwd."""

import subprocess
from pathlib import Path

import click

from agent_kit.config import load_config
from agent_kit.errors import handle_errors, output


def resolve_project_name(config: dict) -> tuple[str, str]:
    """Resolve the current project name and detection source.

    Returns (name, source) where source is one of:
    'project_dir', 'git_remote', 'cwd'.
    """
    cwd = Path.cwd().resolve()
    project_dir = Path(config.get("project_dir", "~/dev")).expanduser().resolve()

    # 1. First subdirectory under project_dir
    try:
        relative = cwd.relative_to(project_dir)
        return relative.parts[0], "project_dir"
    except (ValueError, IndexError):
        pass

    # 2. Git remote repo name
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Handle both SSH and HTTPS: extract repo name without .git
            name = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
            if name:
                return name, "git_remote"
    except FileNotFoundError:
        pass

    # 3. Current directory name
    return cwd.name, "cwd"


@click.command()
@click.option("--config", "with_config", is_flag=True, help="Include brain project config")
@handle_errors
def project(with_config: bool) -> None:
    """Detect the current project.

    Resolves from project_dir, git remote, or current directory name.
    Use --config to include brain project configuration if available.
    """
    config = load_config()
    name, source = resolve_project_name(config)

    result = {"name": name, "source": source}

    if with_config:
        from agent_kit.brain.client import find_project, resolve_brain_dir

        brain_dir = resolve_brain_dir(config)
        if brain_dir.exists():
            brain_config = find_project(brain_dir, name)
            if brain_config:
                result["brain"] = brain_config

    output(result)
