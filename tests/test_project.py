"""Tests for agent_kit.project.resolve_project_name."""

from unittest.mock import MagicMock, patch

from agent_kit.project import resolve_project_name


class TestResolveProjectName:
    def test_project_dir_match(self, tmp_path):
        """CWD under project_dir returns first subdirectory name."""
        project_dir = tmp_path / "dev"
        cwd = project_dir / "archie" / "src"
        cwd.mkdir(parents=True)
        config = {"project_dir": str(project_dir)}
        with patch("agent_kit.project.Path.cwd", return_value=cwd):
            name, source = resolve_project_name(config)
        assert name == "archie"
        assert source == "project_dir"

    @patch("agent_kit.project.subprocess.run")
    def test_git_remote_ssh(self, mock_run, tmp_path):
        """Falls back to git remote when not under project_dir."""
        mock_run.return_value = MagicMock(returncode=0, stdout="git@github.com:user/my-repo.git\n")
        config = {"project_dir": str(tmp_path / "other")}
        with patch("agent_kit.project.Path.cwd", return_value=tmp_path):
            name, source = resolve_project_name(config)
        assert name == "my-repo"
        assert source == "git_remote"

    @patch("agent_kit.project.subprocess.run")
    def test_git_remote_https(self, mock_run, tmp_path):
        """HTTPS remote URL is parsed correctly."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="https://github.com/user/my-repo.git\n"
        )
        config = {"project_dir": str(tmp_path / "other")}
        with patch("agent_kit.project.Path.cwd", return_value=tmp_path):
            name, source = resolve_project_name(config)
        assert name == "my-repo"
        assert source == "git_remote"

    @patch("agent_kit.project.subprocess.run")
    def test_git_remote_no_suffix(self, mock_run, tmp_path):
        """Remote URL without .git suffix."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="https://github.com/user/my-repo\n"
        )
        config = {"project_dir": str(tmp_path / "other")}
        with patch("agent_kit.project.Path.cwd", return_value=tmp_path):
            name, source = resolve_project_name(config)
        assert name == "my-repo"

    @patch("agent_kit.project.subprocess.run")
    def test_cwd_fallback(self, mock_run, tmp_path):
        """Falls back to cwd name when git remote fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        config = {"project_dir": str(tmp_path / "other")}
        with patch("agent_kit.project.Path.cwd", return_value=tmp_path):
            name, source = resolve_project_name(config)
        assert name == tmp_path.name
        assert source == "cwd"

    @patch("agent_kit.project.subprocess.run", side_effect=FileNotFoundError)
    def test_git_not_installed(self, mock_run, tmp_path):
        """Falls back to cwd when git is not installed."""
        config = {"project_dir": str(tmp_path / "other")}
        with patch("agent_kit.project.Path.cwd", return_value=tmp_path):
            name, source = resolve_project_name(config)
        assert name == tmp_path.name
        assert source == "cwd"

    @patch("agent_kit.project.subprocess.run")
    def test_git_remote_empty_name(self, mock_run, tmp_path):
        """Empty repo name from remote falls through to cwd."""
        mock_run.return_value = MagicMock(returncode=0, stdout="\n")
        config = {"project_dir": str(tmp_path / "other")}
        with patch("agent_kit.project.Path.cwd", return_value=tmp_path):
            name, source = resolve_project_name(config)
        assert name == tmp_path.name
        assert source == "cwd"

    def test_project_dir_root(self, tmp_path):
        """CWD is exactly project_dir (no subdirectory) falls through."""
        config = {"project_dir": str(tmp_path)}
        with (
            patch("agent_kit.project.Path.cwd", return_value=tmp_path),
            patch("agent_kit.project.subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            name, source = resolve_project_name(config)
        # relative_to succeeds but parts[0] raises IndexError → falls through
        assert source in ("git_remote", "cwd")
