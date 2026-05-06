"""Tests for agent_kit.init."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from agent_kit.init import init


class TestInitCommand:
    def setup_method(self):
        self.runner = CliRunner()

    @patch("agent_kit.init.subprocess.run")
    @patch("agent_kit.init.save_config")
    @patch("agent_kit.init.load_config")
    def test_creates_structure(self, mock_load, mock_save, mock_run, tmp_path):
        mock_load.return_value = {"brain": {"dir": str(tmp_path)}}
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = self.runner.invoke(init, ["--user", "simon", "--agent", "archie"])
        assert result.exit_code == 0

        # Directories created
        assert (tmp_path / "_archie").is_dir()
        assert (tmp_path / "_archie" / "memory").is_dir()
        assert (tmp_path / "_inbox").is_dir()
        assert (tmp_path / "simon").is_dir()
        assert (tmp_path / "people").is_dir()
        assert (tmp_path / "projects").is_dir()
        assert (tmp_path / "knowledge").is_dir()

        # Files created
        assert (tmp_path / "BRAIN.md").exists()
        assert (tmp_path / "simon" / "profile.md").exists()
        assert (tmp_path / "_archie" / "memory.md").exists()
        assert (tmp_path / "_archie" / "signals.yaml").exists()

    @patch("agent_kit.init.subprocess.run")
    @patch("agent_kit.init.save_config")
    @patch("agent_kit.init.load_config")
    def test_templates_substituted(self, mock_load, mock_save, mock_run, tmp_path):
        mock_load.return_value = {"brain": {"dir": str(tmp_path)}}
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        self.runner.invoke(init, ["--user", "bob", "--agent", "hal"])

        brain_md = (tmp_path / "BRAIN.md").read_text()
        assert "bob" in brain_md
        assert "hal" in brain_md
        assert "{{USER}}" not in brain_md
        assert "{{AGENT}}" not in brain_md

        profile_md = (tmp_path / "bob" / "profile.md").read_text()
        assert "bob" in profile_md

    @patch("agent_kit.init.subprocess.run")
    @patch("agent_kit.init.save_config")
    @patch("agent_kit.init.load_config")
    def test_persists_config(self, mock_load, mock_save, mock_run, tmp_path):
        mock_load.return_value = {"brain": {"dir": str(tmp_path)}}
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        self.runner.invoke(init, ["--user", "simon", "--agent", "archie"])

        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert saved["user"] == "simon"
        assert saved["agent"] == "archie"

    @patch("agent_kit.init.subprocess.run")
    @patch("agent_kit.init.save_config")
    @patch("agent_kit.init.load_config")
    def test_git_init_called(self, mock_load, mock_save, mock_run, tmp_path):
        mock_load.return_value = {"brain": {"dir": str(tmp_path)}}
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        self.runner.invoke(init, ["--user", "simon", "--agent", "archie"])

        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["git", "init"]
        assert mock_run.call_args[1]["cwd"] == tmp_path

    @patch("agent_kit.init.load_config")
    def test_refuses_non_empty_dir(self, mock_load, tmp_path):
        mock_load.return_value = {"brain": {"dir": str(tmp_path)}}
        (tmp_path / "existing-file.md").write_text("content")

        result = self.runner.invoke(init, ["--user", "simon", "--agent", "archie"])
        assert result.exit_code != 0
        assert "not empty" in result.output
