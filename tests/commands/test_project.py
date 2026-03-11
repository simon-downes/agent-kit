"""Tests for project command."""

from pathlib import Path

from click.testing import CliRunner

from agent_kit.commands.project import main


def test_help():
    """Test help output."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Display the project name" in result.output


def test_project_current_directory(tmp_path):
    """Test project name from current directory."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main)
        assert result.exit_code == 0
        assert result.output.strip()  # Should output something


def test_project_explicit_path(tmp_path):
    """Test project name with explicit path."""
    runner = CliRunner()
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()

    result = runner.invoke(main, [str(project_dir)])
    assert result.exit_code == 0
    # Should use path-based resolution
    assert "my-project" in result.output.strip()


def test_project_git_root(tmp_path):
    """Test project name from git root."""
    runner = CliRunner()
    git_dir = tmp_path / "my-project"
    git_dir.mkdir()
    (git_dir / ".git").mkdir()

    result = runner.invoke(main, [str(git_dir)])
    assert result.exit_code == 0
    assert result.output.strip() == "my-project"

