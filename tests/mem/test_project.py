"""Tests for project resolution."""

import tempfile
from pathlib import Path

import pytest

from agent_kit.project import resolve_project


def test_resolve_from_dev_directory(monkeypatch):
    """Test resolution from ~/dev subdirectory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dev_dir = Path(tmpdir) / "dev"
        project_dir = dev_dir / "my-project" / "src"
        project_dir.mkdir(parents=True)

        result = resolve_project(cwd=project_dir, home=Path(tmpdir))
        assert result == "my-project"


def test_resolve_from_git_root(monkeypatch):
    """Test resolution from git repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        git_dir = Path(tmpdir) / "my-repo" / "src" / "module"
        git_dir.mkdir(parents=True)
        (Path(tmpdir) / "my-repo" / ".git").mkdir()

        result = resolve_project(cwd=git_dir, home=Path(tmpdir))
        assert result == "my-repo"


def test_resolve_from_path(monkeypatch):
    """Test fallback to path-based resolution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / "some" / "nested" / "path"
        project_dir.mkdir(parents=True)

        result = resolve_project(cwd=project_dir, home=Path(tmpdir))
        assert "some-nested-path" in result


def test_resolve_dev_takes_precedence(monkeypatch):
    """Test that ~/dev resolution takes precedence over git."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dev_dir = Path(tmpdir) / "dev"
        project_dir = dev_dir / "my-project" / "src"
        project_dir.mkdir(parents=True)
        (dev_dir / "my-project" / ".git").mkdir()

        result = resolve_project(cwd=project_dir, home=Path(tmpdir))
        assert result == "my-project"
