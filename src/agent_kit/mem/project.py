"""Project name resolution."""

import os
from pathlib import Path


def resolve_project(cwd: Path | None = None, home: Path | None = None) -> str:
    """Resolve project name from current directory.

    Resolution order:
    1. First subdirectory under ~/dev if cwd is under ~/dev
    2. First ancestor with .git directory (git project root)
    3. Current directory with path separators replaced with hyphens

    Args:
        cwd: Current working directory (defaults to Path.cwd())
        home: Home directory (defaults to Path.home())

    Returns:
        Project name in kebab-case format.
    """
    if cwd is None:
        cwd = Path.cwd()
    if home is None:
        home = Path.home()

    dev_dir = home / "dev"

    # Check if under ~/dev
    try:
        relative = cwd.relative_to(dev_dir)
        parts = relative.parts
        if parts:
            return parts[0]
    except ValueError:
        pass

    # Check for git root
    current = cwd
    while current != current.parent:
        if (current / ".git").exists():
            return current.name
        current = current.parent

    # Fallback to current directory path
    path_str = str(cwd)
    if path_str.startswith("/"):
        path_str = path_str[1:]
    return path_str.replace(os.sep, "-")
