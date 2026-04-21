"""Tests for agent_kit.brain.cli."""

import json
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agent_kit.brain.client import ENTITY_DIRS, RAW_DIRS, BrainClient
from agent_kit.brain.cli import brain


def _setup_brain(tmp_path, contexts=None):
    """Create a minimal brain directory for testing."""
    for d in RAW_DIRS:
        (tmp_path / "_raw" / d).mkdir(parents=True, exist_ok=True)
    for d in ("_inbox", "_outbox", "_memory"):
        (tmp_path / d).mkdir(exist_ok=True)
    for name in contexts or ["shared"]:
        ctx = tmp_path / name
        for ed in ENTITY_DIRS:
            (ctx / ed).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture(autouse=True)
def _patch_config(tmp_path):
    cfg = {"brain": {"dir": str(tmp_path), "contexts": {}}, "project_dir": "~/dev"}
    with (
        patch("agent_kit.brain.cli.load_config", return_value=cfg),
        patch("agent_kit.brain.cli._get_client", return_value=BrainClient(tmp_path)),
    ):
        yield cfg


class TestInitCommand:
    @patch("agent_kit.brain.git.subprocess.run")
    def test_init_all(self, mock_run, cli_runner, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = cli_runner.invoke(brain, ["init"])
        assert result.exit_code == 0
        assert "shared" in result.output or "created" in result.output

    @patch("agent_kit.brain.git.subprocess.run")
    def test_init_specific_context(self, mock_run, cli_runner, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = cli_runner.invoke(brain, ["init", "work"])
        assert result.exit_code == 0

    def test_init_already_exists(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        result = cli_runner.invoke(brain, ["init", "shared"])
        assert result.exit_code == 0
        assert "already exists" in result.output


class TestIndexCommand:
    def test_list_contexts(self, cli_runner, tmp_path):
        _setup_brain(tmp_path, ["shared", "work"])
        result = cli_runner.invoke(brain, ["index"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "shared" in data
        assert "work" in data

    def test_show_context_index(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        idx = {"contacts": {"alice": {"name": "Alice", "path": "contacts/alice.md"}}}
        (tmp_path / "shared" / "index.yaml").write_text(yaml.dump(idx))
        result = cli_runner.invoke(brain, ["index", "shared"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "contacts" in data

    def test_filter_by_type(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        idx = {
            "contacts": {"alice": {"name": "Alice", "path": "contacts/alice.md"}},
            "projects": {"archie": {"name": "Archie", "path": "projects/archie/"}},
        }
        (tmp_path / "shared" / "index.yaml").write_text(yaml.dump(idx))
        result = cli_runner.invoke(brain, ["index", "shared", "--type", "contacts"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "contacts" in data
        assert "projects" not in data

    def test_filter_by_slug(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        idx = {"contacts": {"alice": {"name": "Alice", "path": "contacts/alice.md"}}}
        (tmp_path / "shared" / "index.yaml").write_text(yaml.dump(idx))
        result = cli_runner.invoke(brain, ["index", "shared", "--slug", "alice"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "alice" in data.get("contacts", {})

    def test_context_not_found(self, cli_runner, tmp_path):
        result = cli_runner.invoke(brain, ["index", "nope"])
        assert result.exit_code != 0


class TestSearchCommand:
    def test_search(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        idx = {"contacts": {"alice": {"name": "Alice", "path": "contacts/alice.md", "summary": "", "tags": []}}}
        (tmp_path / "shared" / "index.yaml").write_text(yaml.dump(idx))
        (tmp_path / "shared" / "contacts" / "alice.md").write_text("Alice")
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            result = cli_runner.invoke(brain, ["search", "alice"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) >= 1
        assert data[0]["slug"] == "alice"

    def test_search_with_context(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        idx = {"contacts": {"alice": {"name": "Alice", "path": "contacts/alice.md", "summary": "", "tags": []}}}
        (tmp_path / "shared" / "index.yaml").write_text(yaml.dump(idx))
        (tmp_path / "shared" / "contacts" / "alice.md").write_text("Alice")
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            result = cli_runner.invoke(brain, ["search", "alice", "--context", "shared"])
        assert result.exit_code == 0


class TestReindexCommand:
    @patch("fcntl.flock")
    def test_reindex(self, mock_flock, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        (tmp_path / "shared" / "contacts" / "alice.md").write_text(
            "---\nname: Alice\n---\nContent"
        )
        result = cli_runner.invoke(brain, ["reindex", "shared"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "contacts" in data

    def test_reindex_not_found(self, cli_runner, tmp_path):
        result = cli_runner.invoke(brain, ["reindex", "nope"])
        assert result.exit_code != 0


class TestCommitCommand:
    @patch("agent_kit.brain.git.subprocess.run")
    def test_commit(self, mock_run, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=" M file.md\n"),
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=0, stdout="abc1234\n"),
        ]
        result = cli_runner.invoke(brain, ["commit", "shared", "-m", "update"])
        assert result.exit_code == 0
        assert "abc1234" in result.output

    @patch("agent_kit.brain.git.subprocess.run")
    def test_nothing_to_commit(self, mock_run, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = cli_runner.invoke(brain, ["commit", "shared", "-m", "update"])
        assert result.exit_code == 0
        assert "nothing to commit" in result.output


class TestProjectCommand:
    def test_project_found(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        proj = tmp_path / "shared" / "projects" / "archie"
        proj.mkdir(parents=True)
        (proj / "README.md").write_text("---\nname: Archie\n---\nContent")
        result = cli_runner.invoke(brain, ["project", "archie"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "Archie"

    def test_project_not_found(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        result = cli_runner.invoke(brain, ["project", "nope"])
        assert result.exit_code != 0


class TestStatusCommand:
    def test_overall_status(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        with patch("agent_kit.brain.git.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = cli_runner.invoke(brain, ["status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "contexts" in data

    def test_context_status(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        with patch("agent_kit.brain.git.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = cli_runner.invoke(brain, ["status", "shared"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["context"] == "shared"


class TestValidateCommand:
    def test_validate_all(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        (tmp_path / "shared" / "index.yaml").write_text(yaml.dump({}))
        with patch("agent_kit.brain.git.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="git@host:repo\n")
            result = cli_runner.invoke(brain, ["validate"])
        assert result.exit_code == 0

    def test_validate_single_context(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        result = cli_runner.invoke(brain, ["validate", "shared"])
        assert result.exit_code == 0

    def test_validate_errors_exit_1(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        idx = {"contacts": {"alice": "not a mapping"}}
        (tmp_path / "shared" / "index.yaml").write_text(yaml.dump(idx))
        result = cli_runner.invoke(brain, ["validate", "shared"])
        assert result.exit_code == 1
