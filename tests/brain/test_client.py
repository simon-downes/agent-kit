"""Tests for agent_kit.brain.client."""

from unittest.mock import MagicMock, patch

import pytest
import yaml

from agent_kit.brain.client import BrainClient, resolve_brain_dir, validate_name
from agent_kit.brain.index import _extract_metadata, _parse_frontmatter, _slug_to_name

# --- resolve / helpers ---


class TestResolveBrainDir:
    def test_default(self):
        assert "brain" in str(resolve_brain_dir({}))

    def test_from_config(self):
        result = resolve_brain_dir({"brain": {"dir": "/tmp/mybrain"}})
        assert str(result) == "/tmp/mybrain"


class TestValidateName:
    def test_valid(self):
        validate_name("shared")

    @pytest.mark.parametrize("name", ["", ".hidden", "a/b", "a..b"])
    def test_invalid(self, name):
        with pytest.raises(ValueError, match="invalid name"):
            validate_name(name)


# --- load_index / query_index ---


class TestLoadIndex:
    def test_loads_yaml(self, tmp_path):
        idx = {"people": {"alice": {"name": "Alice", "path": "people/alice.md"}}}
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        assert BrainClient(tmp_path).load_index() == idx

    def test_missing_returns_empty(self, tmp_path):
        assert BrainClient(tmp_path).load_index() == {}

    def test_invalid_yaml_raises(self, tmp_path):
        (tmp_path / "index.yaml").write_text(":\n  :\n  - :\n  bad: [")
        with pytest.raises(ValueError, match="invalid index.yaml"):
            BrainClient(tmp_path).load_index()


class TestQueryIndex:
    def setup_method(self):
        self.index = {
            "people": {"alice": {"name": "Alice"}},
            "projects": {"archie": {"name": "Archie"}},
        }
        self.client = BrainClient(None)

    def test_no_filter(self):
        assert self.client.query_index(self.index) == self.index

    def test_by_type(self):
        assert self.client.query_index(self.index, entity_type="people") == {
            "people": {"alice": {"name": "Alice"}}
        }

    def test_by_type_missing(self):
        assert self.client.query_index(self.index, entity_type="goals") == {}

    def test_by_slug(self):
        assert self.client.query_index(self.index, slug="archie") == {
            "projects": {"archie": {"name": "Archie"}}
        }

    def test_by_slug_missing(self):
        assert self.client.query_index(self.index, slug="nope") == {}


# --- search ---


class TestSearch:
    def test_name_match(self, tmp_path):
        idx = {"people": {"alice": {"name": "Alice", "path": "people/alice.md", "summary": "", "tags": []}}}
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        (tmp_path / "people").mkdir()
        (tmp_path / "people" / "alice.md").write_text("Alice")
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            results = BrainClient(tmp_path).search(["alice"])
        assert len(results) >= 1
        assert results[0]["name"] == "Alice"
        assert results[0]["score"] == 3

    def test_tag_match(self, tmp_path):
        idx = {"people": {"bob": {"name": "Bob", "path": "people/bob.md", "summary": "", "tags": ["engineer"]}}}
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        (tmp_path / "people").mkdir()
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            results = BrainClient(tmp_path).search(["engineer"])
        assert results[0]["score"] == 2

    def test_summary_match(self, tmp_path):
        idx = {"projects": {"archie": {"name": "Archie", "path": "projects/archie/", "summary": "personal AI platform", "tags": []}}}
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        (tmp_path / "projects").mkdir()
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            results = BrainClient(tmp_path).search(["platform"])
        assert results[0]["score"] == 1

    def test_multiple_terms_boost(self, tmp_path):
        idx = {
            "people": {
                "alice": {"name": "Alice", "path": "people/alice.md", "summary": "engineer", "tags": ["eng"]},
                "bob": {"name": "Bob", "path": "people/bob.md", "summary": "", "tags": []},
            }
        }
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        (tmp_path / "people").mkdir()
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            results = BrainClient(tmp_path).search(["alice", "eng"])
        # Alice matches both terms
        assert results[0]["name"] == "Alice"
        assert results[0]["matches"] == 2

    def test_content_match_from_rg(self, tmp_path):
        (tmp_path / "index.yaml").write_text(yaml.dump({}))
        (tmp_path / "knowledge").mkdir()
        rg_hit = {"path": "knowledge/aws.md", "name": "Aws", "modified": 100.0}
        with patch("agent_kit.brain.search._rg_search", return_value=[rg_hit]):
            results = BrainClient(tmp_path).search(["aurora"])
        assert len(results) == 1
        assert results[0]["score"] == 1

    def test_limits_results(self, tmp_path):
        entries = {}
        for i in range(30):
            entries[f"item{i}"] = {"name": f"test item{i}", "path": f"people/{i}.md", "summary": "", "tags": []}
        (tmp_path / "index.yaml").write_text(yaml.dump({"people": entries}))
        (tmp_path / "people").mkdir()
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            results = BrainClient(tmp_path).search(["test"], limit=5)
        assert len(results) == 5


# --- reference tracking ---


class TestRefTracking:
    def test_record_and_query(self, tmp_path):
        client = BrainClient(tmp_path)
        client.record_ref("people/alice.md")
        client.record_ref("people/alice.md")
        client.record_ref("people/bob.md")
        top = client.top_refs(10)
        assert top[0]["path"] == "people/alice.md"
        assert top[0]["count"] == 2

    def test_stale_refs(self, tmp_path):
        idx = {"people": {"alice": {"name": "Alice", "path": "people/alice.md"}}}
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        client = BrainClient(tmp_path)
        # No refs recorded — alice should be stale
        stale = client.stale_refs(since_days=0)
        assert any(r["path"] == "people/alice.md" for r in stale)


# --- status ---


class TestBrainStatus:
    def test_status(self, tmp_path):
        (tmp_path / "_inbox").mkdir()
        (tmp_path / "people").mkdir()
        with patch("agent_kit.brain.git.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = BrainClient(tmp_path).brain_status()
        assert result["dir"] == str(tmp_path)
        assert "directories" in result


# --- commit ---


class TestCommit:
    @patch("agent_kit.brain.git.subprocess.run")
    def test_commits_all(self, mock_run, tmp_path):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=" M file.md\n"),
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=0, stdout="abc1234\n"),
        ]
        sha = BrainClient(tmp_path).commit("update")
        assert sha == "abc1234"

    @patch("agent_kit.brain.git.subprocess.run")
    def test_nothing_to_commit(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert BrainClient(tmp_path).commit("update") is None


# --- find_project ---


class TestFindProject:
    def test_finds_project_dir(self, tmp_path):
        proj = tmp_path / "projects" / "archie"
        proj.mkdir(parents=True)
        (proj / "README.md").write_text("---\nname: Archie\n---\nContent")
        result = BrainClient(tmp_path).find_project("archie")
        assert result["name"] == "Archie"
        assert result["path"] == "projects/archie/"

    def test_finds_project_file(self, tmp_path):
        (tmp_path / "projects").mkdir()
        (tmp_path / "projects" / "archie.md").write_text("---\nname: Archie\n---\nContent")
        result = BrainClient(tmp_path).find_project("archie")
        assert result["name"] == "Archie"
        assert result["path"] == "projects/archie.md"

    def test_not_found(self, tmp_path):
        (tmp_path / "projects").mkdir()
        assert BrainClient(tmp_path).find_project("nope") is None


# --- reindex ---


class TestReindex:
    @patch("fcntl.flock")
    def test_indexes_files(self, mock_flock, tmp_path):
        (tmp_path / "people").mkdir()
        (tmp_path / "people" / "alice.md").write_text("---\nname: Alice\n---\nContent")
        result = BrainClient(tmp_path).reindex()
        assert "people" in result
        assert "alice" in result["people"]


# --- _parse_frontmatter ---


class TestParseFrontmatter:
    def test_extracts_yaml(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\nname: Alice\nsummary: A contact\n---\nContent here")
        assert _parse_frontmatter(f) == {"name": "Alice", "summary": "A contact"}

    def test_no_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("Just content")
        assert _parse_frontmatter(f) == {}

    def test_invalid_yaml_returns_empty(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\nbad: [\n---\nContent")
        assert _parse_frontmatter(f) == {}


# --- _extract_metadata ---


class TestExtractMetadata:
    def test_markdown_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\nname: Test\n---\nContent")
        assert _extract_metadata(f)["name"] == "Test"

    def test_yaml_file(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("name: Test\nsummary: A thing")
        assert _extract_metadata(f)["name"] == "Test"

    def test_directory_with_readme(self, tmp_path):
        d = tmp_path / "proj"
        d.mkdir()
        (d / "README.md").write_text("---\nname: My Project\n---\nContent")
        assert _extract_metadata(d)["name"] == "My Project"

    def test_directory_without_readme(self, tmp_path):
        d = tmp_path / "proj"
        d.mkdir()
        assert _extract_metadata(d) == {}


# --- _slug_to_name ---


class TestSlugToName:
    def test_hyphens(self):
        assert _slug_to_name("bob-jones") == "Bob Jones"

    def test_underscores(self):
        assert _slug_to_name("bob_jones") == "Bob Jones"


# --- memory indexing and age decay ---


class TestMemoryIndexing:
    @patch("fcntl.flock")
    def test_reindex_includes_memory(self, mock_flock, tmp_path):
        mem_dir = tmp_path / "_archie" / "memory"
        mem_dir.mkdir(parents=True)
        (mem_dir / "2026-05-01-archie.md").write_text(
            "---\nname: Archie session\nsummary: Worked on brain\ntags: [archie]\n---\nContent"
        )
        result = BrainClient(tmp_path).reindex()
        assert "memory" in result
        assert "2026-05-01-archie" in result["memory"]
        assert result["memory"]["2026-05-01-archie"]["name"] == "Archie session"

    def test_search_includes_memory_dir(self, tmp_path):
        """Memory dir is included in rg search paths even though _archie is excluded."""
        mem_dir = tmp_path / "_archie" / "memory"
        mem_dir.mkdir(parents=True)
        (tmp_path / "people").mkdir()
        idx = {"memory": {"2026-05-01-archie": {
            "name": "Archie session",
            "path": "_archie/memory/2026-05-01-archie.md",
            "summary": "brain work",
            "tags": ["archie"],
        }}}
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        with patch("agent_kit.brain.search._rg_search", return_value=[]) as mock_rg:
            BrainClient(tmp_path).search(["archie"])
            # Verify _archie/memory was in the search paths
            call_args = mock_rg.call_args[0]
            search_paths = call_args[1]
            assert any("_archie/memory" in p for p in search_paths)


class TestMemoryAgeDecay:
    def _make_memory_index(self, tmp_path, filename):
        slug = filename.replace(".md", "")
        idx = {"memory": {slug: {
            "name": "Session notes",
            "path": f"_archie/memory/{filename}",
            "summary": "worked on things",
            "tags": ["archie"],
        }}}
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        mem_dir = tmp_path / "_archie" / "memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        return idx

    def test_recent_memory_boosted(self, tmp_path):
        from datetime import date, timedelta

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        filename = f"{yesterday}-work.md"
        self._make_memory_index(tmp_path, filename)
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            results = BrainClient(tmp_path).search(["archie"])
        # Tag match (2) + age boost (2) = 4
        assert results[0]["score"] == 4

    def test_old_memory_penalised(self, tmp_path):
        from datetime import date, timedelta

        old_date = (date.today() - timedelta(days=120)).isoformat()
        filename = f"{old_date}-work.md"
        self._make_memory_index(tmp_path, filename)
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            results = BrainClient(tmp_path).search(["archie"])
        # Tag match (2) + age penalty (-1) = 1
        assert results[0]["score"] == 1

    def test_mid_age_memory_small_boost(self, tmp_path):
        from datetime import date, timedelta

        mid_date = (date.today() - timedelta(days=14)).isoformat()
        filename = f"{mid_date}-work.md"
        self._make_memory_index(tmp_path, filename)
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            results = BrainClient(tmp_path).search(["archie"])
        # Tag match (2) + age boost (1) = 3
        assert results[0]["score"] == 3

    def test_no_date_in_filename_neutral(self, tmp_path):
        self._make_memory_index(tmp_path, "random-notes.md")
        with patch("agent_kit.brain.search._rg_search", return_value=[]):
            results = BrainClient(tmp_path).search(["archie"])
        # Tag match (2) + no age modifier = 2
        assert results[0]["score"] == 2

    def test_type_memory_filter(self, tmp_path):
        idx = {
            "people": {"alice": {"name": "Alice", "path": "people/alice.md"}},
            "memory": {"2026-05-01-test": {"name": "Test", "path": "_archie/memory/2026-05-01-test.md"}},
        }
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        client = BrainClient(tmp_path)
        result = client.query_index(idx, entity_type="memory")
        assert "memory" in result
        assert "people" not in result
