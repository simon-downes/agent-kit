"""Tests for agent_kit.brain.cli."""

import json
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agent_kit.brain.cli import brain
from agent_kit.brain.client import BrainClient


@pytest.fixture
def cli_runner():
    from click.testing import CliRunner

    return CliRunner()


@pytest.fixture(autouse=True)
def _patch_config(tmp_path):
    cfg = {"brain": {"dir": str(tmp_path)}, "project_dir": "~/dev"}
    with (
        patch("agent_kit.brain.cli.load_config", return_value=cfg),
        patch("agent_kit.brain.cli._get_client", return_value=BrainClient(tmp_path)),
    ):
        yield cfg


def _setup_brain(tmp_path):
    """Create a minimal brain directory for testing."""
    for d in ("_inbox", "people", "projects", "knowledge"):
        (tmp_path / d).mkdir(exist_ok=True)
    return tmp_path


class TestIndexCommand:
    def test_show_index(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        idx = {"people": {"alice": {"name": "Alice", "path": "people/alice.md"}}}
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        result = cli_runner.invoke(brain, ["index"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "people" in data

    def test_filter_by_type(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        idx = {
            "people": {"alice": {"name": "Alice", "path": "people/alice.md"}},
            "projects": {"archie": {"name": "Archie", "path": "projects/archie/"}},
        }
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        result = cli_runner.invoke(brain, ["index", "--type", "people"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "people" in data
        assert "projects" not in data

    def test_filter_by_slug(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        idx = {"people": {"alice": {"name": "Alice", "path": "people/alice.md"}}}
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        result = cli_runner.invoke(brain, ["index", "--slug", "alice"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "alice" in data.get("people", {})


class TestSearchCommand:
    def test_search_single_term(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        idx = {
            "people": {
                "alice": {"name": "Alice", "path": "people/alice.md", "summary": "", "tags": []}
            }
        }
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        (tmp_path / "people" / "alice.md").write_text("Alice is a developer")
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            result = cli_runner.invoke(brain, ["search", "alice"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) >= 1
        assert data[0]["name"] == "Alice"

    def test_search_multiple_terms(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        idx = {
            "people": {
                "alice": {
                    "name": "Alice",
                    "path": "people/alice.md",
                    "summary": "developer",
                    "tags": ["eng"],
                },
                "bob": {"name": "Bob", "path": "people/bob.md", "summary": "manager", "tags": []},
            }
        }
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            result = cli_runner.invoke(brain, ["search", "alice", "eng"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        # Alice matches both terms (name + tag), should rank higher
        assert data[0]["name"] == "Alice"
        assert data[0]["matches"] == 2


class TestReindexCommand:
    @patch("fcntl.flock")
    def test_reindex(self, mock_flock, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        (tmp_path / "people").mkdir(exist_ok=True)
        (tmp_path / "people" / "alice.md").write_text("---\nname: Alice\n---\nContent")
        result = cli_runner.invoke(brain, ["reindex"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "people" in data


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
        result = cli_runner.invoke(brain, ["commit", "update"])
        assert result.exit_code == 0
        assert "abc1234" in result.output

    @patch("agent_kit.brain.git.subprocess.run")
    def test_nothing_to_commit(self, mock_run, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = cli_runner.invoke(brain, ["commit", "update"])
        assert result.exit_code == 0
        assert "nothing to commit" in result.output


class TestRefCommand:
    def test_record_ref(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        result = cli_runner.invoke(brain, ["ref", "people/alice.md"])
        assert result.exit_code == 0

    def test_refs_top(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        client = BrainClient(tmp_path)
        client.record_ref("people/alice.md")
        client.record_ref("people/alice.md")
        client.record_ref("people/bob.md")
        result = cli_runner.invoke(brain, ["refs", "--top", "5"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["path"] == "people/alice.md"
        assert data[0]["count"] == 2


class TestProjectCommand:
    def test_project_found(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        proj = tmp_path / "projects" / "archie"
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
    def test_status(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        with patch("agent_kit.brain.git.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = cli_runner.invoke(brain, ["status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "dir" in data


class TestReadCommand:
    def test_reads_file(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        (tmp_path / "people" / "alice.md").write_text("# Alice\nSome content")
        result = cli_runner.invoke(brain, ["read", "people/alice.md"])
        assert result.exit_code == 0
        assert "# Alice" in result.output
        assert "Some content" in result.output

    def test_not_found(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        result = cli_runner.invoke(brain, ["read", "nonexistent.md"])
        assert result.exit_code != 0

    def test_path_traversal(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        result = cli_runner.invoke(brain, ["read", "../../etc/passwd"])
        assert result.exit_code != 0


class TestMemoryCommand:
    def _setup_memories(self, tmp_path):
        mem_dir = tmp_path / "_archie" / "memory"
        mem_dir.mkdir(parents=True)
        (mem_dir / "2026-05-29-apps-4208.md").write_text(
            "---\nname: Apps session\nsummary: Did stuff\ntags: [apps]\n---\nApps content"
        )
        (mem_dir / "2026-05-28-archie-1234.md").write_text(
            "---\nname: Archie session\nsummary: Platform\ntags: [archie]\n---\nArchie content"
        )

    def test_returns_recent(self, cli_runner, tmp_path):
        self._setup_memories(tmp_path)
        result = cli_runner.invoke(brain, ["memory"])
        assert result.exit_code == 0
        assert "Apps session" in result.output
        assert "Archie session" in result.output

    def test_filters_by_project(self, cli_runner, tmp_path):
        self._setup_memories(tmp_path)
        result = cli_runner.invoke(brain, ["memory", "--project", "apps"])
        assert result.exit_code == 0
        assert "Apps session" in result.output
        assert "Archie session" not in result.output

    def test_respects_limit(self, cli_runner, tmp_path):
        self._setup_memories(tmp_path)
        result = cli_runner.invoke(brain, ["memory", "--limit", "1"])
        assert result.exit_code == 0
        assert "Apps session" in result.output
        assert "Archie session" not in result.output


class TestSearchTypeFilter:
    def test_search_with_type_filter(self, cli_runner, tmp_path):
        _setup_brain(tmp_path)
        idx = {
            "people": {
                "alice": {"name": "Alice", "path": "people/alice.md", "summary": "", "tags": []}
            },
            "memory": {
                "2026-05-01-alice": {
                    "name": "Alice session",
                    "path": "_archie/memory/2026-05-01-alice.md",
                    "summary": "",
                    "tags": ["alice"],
                }
            },
        }
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        mem_dir = tmp_path / "_archie" / "memory"
        mem_dir.mkdir(parents=True)
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            result = cli_runner.invoke(brain, ["search", "alice", "--type", "people"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert all(r.get("type") == "people" for r in data)
