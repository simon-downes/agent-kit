"""Tests for agent_kit.brain.client."""

from unittest.mock import MagicMock, patch

import pytest
import yaml

from agent_kit.brain.client import (
    ENTITY_DIRS,
    INDEXABLE_DIRS,
    RAW_DIRS,
    _extract_metadata,
    _match_weight,
    _parse_frontmatter,
    _slug_to_name,
    brain_status,
    commit_context,
    configured_contexts,
    context_status,
    find_project,
    init_brain,
    init_context,
    list_contexts,
    load_index,
    query_index,
    reindex_context,
    resolve_brain_dir,
    search_brain,
    validate_context,
    validate_name,
    validate_origins,
)


# --- resolve / config helpers ---


class TestResolveBrainDir:
    def test_default(self):
        assert "brain" in str(resolve_brain_dir({}))

    def test_from_config(self):
        result = resolve_brain_dir({"brain": {"dir": "/tmp/mybrain"}})
        assert str(result) == "/tmp/mybrain"


class TestConfiguredContexts:
    def test_returns_contexts(self):
        cfg = {"brain": {"contexts": {"work": "git@host:repo"}}}
        assert configured_contexts(cfg) == {"work": "git@host:repo"}

    def test_empty(self):
        assert configured_contexts({}) == {}


# --- validate_name ---


class TestValidateName:
    def test_valid(self):
        validate_name("shared")  # no error

    @pytest.mark.parametrize("name", ["", ".hidden", "a/b", "a..b"])
    def test_invalid(self, name):
        with pytest.raises(ValueError, match="invalid context name"):
            validate_name(name)


# --- list_contexts ---


class TestListContexts:
    def test_lists_dirs(self, tmp_path):
        (tmp_path / "work").mkdir()
        (tmp_path / "shared").mkdir()
        (tmp_path / "_memory").mkdir()
        (tmp_path / ".git").mkdir()
        assert list_contexts(tmp_path) == ["shared", "work"]

    def test_missing_dir(self, tmp_path):
        assert list_contexts(tmp_path / "nope") == []


# --- load_index / query_index ---


class TestLoadIndex:
    def test_loads_yaml(self, tmp_path):
        idx = {"contacts": {"alice": {"name": "Alice", "path": "contacts/alice.md"}}}
        (tmp_path / "index.yaml").write_text(yaml.dump(idx))
        assert load_index(tmp_path) == idx

    def test_missing_returns_empty(self, tmp_path):
        assert load_index(tmp_path) == {}

    def test_invalid_yaml_raises(self, tmp_path):
        (tmp_path / "index.yaml").write_text(":\n  :\n  - :\n  bad: [")
        with pytest.raises(ValueError, match="invalid index.yaml"):
            load_index(tmp_path)


class TestQueryIndex:
    def setup_method(self):
        self.index = {
            "contacts": {"alice": {"name": "Alice"}},
            "projects": {"archie": {"name": "Archie"}},
        }

    def test_no_filter(self):
        assert query_index(self.index) == self.index

    def test_by_type(self):
        assert query_index(self.index, entity_type="contacts") == {
            "contacts": {"alice": {"name": "Alice"}}
        }

    def test_by_type_missing(self):
        assert query_index(self.index, entity_type="goals") == {}

    def test_by_slug(self):
        assert query_index(self.index, slug="archie") == {
            "projects": {"archie": {"name": "Archie"}}
        }

    def test_by_slug_missing(self):
        assert query_index(self.index, slug="nope") == {}


# --- init_brain / init_context ---


class TestInitContext:
    @patch("agent_kit.brain.client.subprocess.run")
    def test_creates_local(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = init_context(tmp_path, "shared")
        assert result == "created shared"
        assert (tmp_path / "shared" / "contacts").is_dir()
        mock_run.assert_called_once()

    @patch("agent_kit.brain.client.subprocess.run")
    def test_clones_repo(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = init_context(tmp_path, "work", "git@host:repo")
        assert result == "cloned work from git@host:repo"

    @patch("agent_kit.brain.client.subprocess.run")
    def test_clone_failure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stderr="fatal: repo not found")
        with pytest.raises(ValueError, match="git clone failed"):
            init_context(tmp_path, "work", "git@host:bad")

    def test_already_exists(self, tmp_path):
        (tmp_path / "shared").mkdir()
        assert init_context(tmp_path, "shared") is None

    def test_invalid_name(self, tmp_path):
        with pytest.raises(ValueError, match="invalid context name"):
            init_context(tmp_path, ".bad")

    @patch("agent_kit.brain.client.subprocess.run")
    def test_git_init_failure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stderr="git init failed")
        with pytest.raises(ValueError, match="git init failed"):
            init_context(tmp_path, "shared")


class TestInitBrain:
    @patch("agent_kit.brain.client.subprocess.run")
    def test_creates_structure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        actions = init_brain(tmp_path, {"brain": {"contexts": {}}})
        # Should create _raw dirs, operational dirs, and shared context
        assert any("inbox" in a for a in actions)
        assert any("shared" in a for a in actions)
        assert (tmp_path / "_raw" / "inbox").is_dir()
        assert (tmp_path / "_memory").is_dir()


# --- context_status / brain_status ---


class TestContextStatus:
    @patch("agent_kit.brain.client.subprocess.run")
    def test_clean(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = context_status(tmp_path)
        assert result["changes"] == []

    @patch("agent_kit.brain.client.subprocess.run")
    def test_with_changes(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout=" M file.md\n?? new.md\n")
        result = context_status(tmp_path)
        assert len(result["changes"]) == 2

    @patch("agent_kit.brain.client.subprocess.run")
    def test_not_git_repo(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=128, stdout="")
        result = context_status(tmp_path)
        assert result["git_error"] == "not a git repository"


class TestBrainStatus:
    def test_includes_raw_and_contexts(self, tmp_path):
        # Set up raw dirs
        for d in RAW_DIRS:
            (tmp_path / "_raw" / d).mkdir(parents=True)
        # Set up a context
        (tmp_path / "shared").mkdir()
        with patch("agent_kit.brain.client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = brain_status(tmp_path)
        assert "raw" in result
        assert len(result["contexts"]) == 1


# --- validate_context ---


class TestValidateContext:
    def test_missing_dirs(self, tmp_path):
        ctx = tmp_path / "test"
        ctx.mkdir()
        findings = validate_context(ctx)
        warnings = [f for f in findings if f["level"] == "warning"]
        assert len(warnings) == len(ENTITY_DIRS)

    def test_no_index(self, tmp_path):
        ctx = tmp_path / "test"
        ctx.mkdir()
        for d in ENTITY_DIRS:
            (ctx / d).mkdir()
        findings = validate_context(ctx)
        assert any(f["message"] == "no index.yaml" for f in findings)

    def test_invalid_index_yaml(self, tmp_path):
        ctx = tmp_path / "test"
        ctx.mkdir()
        for d in ENTITY_DIRS:
            (ctx / d).mkdir()
        (ctx / "index.yaml").write_text("bad: [")
        findings = validate_context(ctx)
        assert any(f["level"] == "error" and "invalid index.yaml" in f["message"] for f in findings)

    def test_missing_path(self, tmp_path):
        ctx = tmp_path / "test"
        ctx.mkdir()
        for d in ENTITY_DIRS:
            (ctx / d).mkdir()
        idx = {"contacts": {"alice": {"name": "Alice", "path": "contacts/alice.md"}}}
        (ctx / "index.yaml").write_text(yaml.dump(idx))
        findings = validate_context(ctx)
        assert any("path not found" in f["message"] for f in findings)

    def test_entry_not_mapping(self, tmp_path):
        ctx = tmp_path / "test"
        ctx.mkdir()
        for d in ENTITY_DIRS:
            (ctx / d).mkdir()
        idx = {"contacts": {"alice": "just a string"}}
        (ctx / "index.yaml").write_text(yaml.dump(idx))
        findings = validate_context(ctx)
        assert any("is not a mapping" in f["message"] for f in findings)

    def test_type_not_mapping(self, tmp_path):
        ctx = tmp_path / "test"
        ctx.mkdir()
        for d in ENTITY_DIRS:
            (ctx / d).mkdir()
        idx = {"contacts": "bad"}
        (ctx / "index.yaml").write_text(yaml.dump(idx))
        findings = validate_context(ctx)
        assert any("is not a mapping" in f["message"] for f in findings)

    def test_missing_name_field(self, tmp_path):
        ctx = tmp_path / "test"
        ctx.mkdir()
        for d in ENTITY_DIRS:
            (ctx / d).mkdir()
        (ctx / "contacts" / "alice.md").write_text("hello")
        idx = {"contacts": {"alice": {"path": "contacts/alice.md"}}}
        (ctx / "index.yaml").write_text(yaml.dump(idx))
        findings = validate_context(ctx)
        assert any("missing 'name'" in f["message"] for f in findings)

    def test_missing_path_field(self, tmp_path):
        ctx = tmp_path / "test"
        ctx.mkdir()
        for d in ENTITY_DIRS:
            (ctx / d).mkdir()
        idx = {"contacts": {"alice": {"name": "Alice"}}}
        (ctx / "index.yaml").write_text(yaml.dump(idx))
        findings = validate_context(ctx)
        assert any("missing 'path'" in f["message"] for f in findings)

    def test_unindexed_entity(self, tmp_path):
        ctx = tmp_path / "test"
        ctx.mkdir()
        for d in ENTITY_DIRS:
            (ctx / d).mkdir()
        (ctx / "contacts" / "bob.md").write_text("hello")
        (ctx / "index.yaml").write_text(yaml.dump({}))
        findings = validate_context(ctx)
        assert any("not indexed" in f["message"] for f in findings)


# --- validate_origins ---


class TestValidateOrigins:
    @patch("agent_kit.brain.client.subprocess.run")
    def test_matching_origin(self, mock_run, tmp_path):
        (tmp_path / "work").mkdir()
        mock_run.return_value = MagicMock(returncode=0, stdout="git@host:repo\n")
        cfg = {"brain": {"contexts": {"work": "git@host:repo"}}}
        findings = validate_origins(tmp_path, cfg)
        assert findings == []

    @patch("agent_kit.brain.client.subprocess.run")
    def test_mismatched_origin(self, mock_run, tmp_path):
        (tmp_path / "work").mkdir()
        mock_run.return_value = MagicMock(returncode=0, stdout="git@host:other\n")
        cfg = {"brain": {"contexts": {"work": "git@host:repo"}}}
        findings = validate_origins(tmp_path, cfg)
        assert any("origin mismatch" in f["message"] for f in findings)

    @patch("agent_kit.brain.client.subprocess.run")
    def test_no_remote(self, mock_run, tmp_path):
        (tmp_path / "work").mkdir()
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        cfg = {"brain": {"contexts": {"work": "git@host:repo"}}}
        findings = validate_origins(tmp_path, cfg)
        assert any("no git remote" in f["message"] for f in findings)

    def test_missing_context(self, tmp_path):
        cfg = {"brain": {"contexts": {"work": "git@host:repo"}}}
        findings = validate_origins(tmp_path, cfg)
        assert any("not found" in f["message"] for f in findings)

    def test_skips_no_repo(self, tmp_path):
        cfg = {"brain": {"contexts": {"shared": None}}}
        assert validate_origins(tmp_path, cfg) == []


# --- reindex_context ---


class TestReindexContext:
    @patch("fcntl.flock")
    def test_indexes_markdown_file(self, mock_flock, tmp_path):
        ctx = tmp_path / "test"
        for d in ENTITY_DIRS:
            (ctx / d).mkdir(parents=True)
        (ctx / "contacts" / "alice.md").write_text(
            "---\nname: Alice Smith\nsummary: A contact\ntags:\n  - friend\n---\nContent"
        )
        result = reindex_context(ctx)
        assert "contacts" in result
        assert "alice" in result["contacts"]
        assert result["contacts"]["alice"]["name"] == "Alice Smith"

    @patch("fcntl.flock")
    def test_preserves_existing_entry(self, mock_flock, tmp_path):
        ctx = tmp_path / "test"
        for d in ENTITY_DIRS:
            (ctx / d).mkdir(parents=True)
        (ctx / "contacts" / "alice.md").write_text("no frontmatter")
        existing = {
            "contacts": {
                "alice": {"name": "Alice Curated", "path": "contacts/alice.md", "summary": "curated"}
            }
        }
        (ctx / "index.yaml").write_text(yaml.dump(existing))
        result = reindex_context(ctx)
        assert result["contacts"]["alice"]["name"] == "Alice Curated"

    @patch("fcntl.flock")
    def test_slug_to_name_fallback(self, mock_flock, tmp_path):
        ctx = tmp_path / "test"
        for d in ENTITY_DIRS:
            (ctx / d).mkdir(parents=True)
        (ctx / "contacts" / "bob-jones.md").write_text("no frontmatter")
        result = reindex_context(ctx)
        assert result["contacts"]["bob-jones"]["name"] == "Bob Jones"

    @patch("fcntl.flock")
    def test_indexes_project_dir(self, mock_flock, tmp_path):
        ctx = tmp_path / "test"
        for d in ENTITY_DIRS:
            (ctx / d).mkdir(parents=True)
        proj = ctx / "projects" / "myapp"
        proj.mkdir()
        (proj / "README.md").write_text("---\nname: My App\n---\nContent")
        result = reindex_context(ctx)
        assert "projects" in result
        assert result["projects"]["myapp"]["name"] == "My App"

    @patch("fcntl.flock")
    def test_indexes_yaml_file(self, mock_flock, tmp_path):
        ctx = tmp_path / "test"
        for d in ENTITY_DIRS:
            (ctx / d).mkdir(parents=True)
        (ctx / "contacts" / "carol.yaml").write_text("name: Carol\nsummary: yaml contact")
        result = reindex_context(ctx)
        assert result["contacts"]["carol"]["name"] == "Carol"

    @patch("fcntl.flock")
    def test_indexes_nested_knowledge(self, mock_flock, tmp_path):
        """Subdirs without README.md are walked for individual files."""
        ctx = tmp_path / "test"
        for d in ENTITY_DIRS:
            (ctx / d).mkdir(parents=True)
        aws_dir = ctx / "knowledge" / "aws"
        aws_dir.mkdir()
        (aws_dir / "aurora.md").write_text("---\nname: Aurora Notes\n---\nContent")
        result = reindex_context(ctx)
        assert "knowledge" in result
        # The slug is the stem of the file
        assert any("aurora" in slug for slug in result["knowledge"])


# --- commit_context ---


class TestCommitContext:
    @patch("agent_kit.brain.client.subprocess.run")
    def test_commits_all(self, mock_run, tmp_path):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=" M file.md\n"),  # status
            MagicMock(returncode=0, stderr=""),  # add -A
            MagicMock(returncode=0, stderr=""),  # commit
            MagicMock(returncode=0, stdout="abc1234\n"),  # rev-parse
        ]
        sha = commit_context(tmp_path, "update")
        assert sha == "abc1234"

    @patch("agent_kit.brain.client.subprocess.run")
    def test_nothing_to_commit(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert commit_context(tmp_path, "update") is None

    @patch("agent_kit.brain.client.subprocess.run")
    def test_specific_paths(self, mock_run, tmp_path):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=" M file.md\n"),
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=0, stdout="def5678\n"),
        ]
        sha = commit_context(tmp_path, "update", ["file.md"])
        assert sha == "def5678"
        # Second call should be git add with specific path
        add_call = mock_run.call_args_list[1]
        assert "file.md" in add_call[0][0]

    @patch("agent_kit.brain.client.subprocess.run")
    def test_add_failure(self, mock_run, tmp_path):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=" M file.md\n"),
            MagicMock(returncode=1, stderr="add failed"),
        ]
        with pytest.raises(ValueError, match="git add failed"):
            commit_context(tmp_path, "update")

    @patch("agent_kit.brain.client.subprocess.run")
    def test_commit_failure(self, mock_run, tmp_path):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=" M file.md\n"),
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=1, stderr="commit failed"),
        ]
        with pytest.raises(ValueError, match="git commit failed"):
            commit_context(tmp_path, "update")


# --- search_brain ---


class TestSearchBrain:
    def _setup_context(self, brain_dir, name="shared"):
        ctx = brain_dir / name
        for d in ENTITY_DIRS:
            (ctx / d).mkdir(parents=True)
        return ctx

    def test_name_match_ranked_first(self, tmp_path):
        ctx = self._setup_context(tmp_path)
        idx = {
            "contacts": {
                "alice": {"name": "Alice", "path": "contacts/alice.md", "summary": "", "tags": []},
                "bob": {"name": "Bob", "path": "contacts/bob.md", "summary": "knows alice", "tags": []},
            }
        }
        (ctx / "index.yaml").write_text(yaml.dump(idx))
        (ctx / "contacts" / "alice.md").write_text("Alice")
        (ctx / "contacts" / "bob.md").write_text("Bob")
        with patch("agent_kit.brain.client._rg_search", return_value=[]):
            results = search_brain(tmp_path, "alice")
        assert len(results) >= 1
        assert results[0]["match"] == "name"
        assert results[0]["slug"] == "alice"

    def test_tag_match(self, tmp_path):
        ctx = self._setup_context(tmp_path)
        idx = {
            "contacts": {
                "bob": {"name": "Bob", "path": "contacts/bob.md", "summary": "", "tags": ["engineer"]},
            }
        }
        (ctx / "index.yaml").write_text(yaml.dump(idx))
        (ctx / "contacts" / "bob.md").write_text("Bob")
        with patch("agent_kit.brain.client._rg_search", return_value=[]):
            results = search_brain(tmp_path, "engineer")
        assert results[0]["match"] == "tag"

    def test_summary_match(self, tmp_path):
        ctx = self._setup_context(tmp_path)
        idx = {
            "projects": {
                "archie": {
                    "name": "Archie",
                    "path": "projects/archie/",
                    "summary": "personal AI platform",
                    "tags": [],
                },
            }
        }
        (ctx / "index.yaml").write_text(yaml.dump(idx))
        (ctx / "projects" / "archie").mkdir()
        with patch("agent_kit.brain.client._rg_search", return_value=[]):
            results = search_brain(tmp_path, "platform")
        assert results[0]["match"] == "summary"

    def test_content_match_from_rg(self, tmp_path):
        ctx = self._setup_context(tmp_path)
        (ctx / "index.yaml").write_text(yaml.dump({}))
        rg_hit = {
            "path": "shared/knowledge/aws.md",
            "name": "Aws",
            "modified": 100.0,
        }
        with patch("agent_kit.brain.client._rg_search", return_value=[rg_hit]):
            results = search_brain(tmp_path, "aurora")
        assert any(r["match"] == "content" for r in results)

    def test_limits_results(self, tmp_path):
        ctx = self._setup_context(tmp_path)
        entries = {}
        for i in range(30):
            slug = f"item{i}"
            entries[slug] = {"name": f"test item{i}", "path": f"contacts/{slug}.md", "summary": "", "tags": []}
        (ctx / "index.yaml").write_text(yaml.dump({"contacts": entries}))
        with patch("agent_kit.brain.client._rg_search", return_value=[]):
            results = search_brain(tmp_path, "test", limit=5)
        assert len(results) == 5

    def test_specific_context(self, tmp_path):
        self._setup_context(tmp_path, "work")
        self._setup_context(tmp_path, "personal")
        idx = {"contacts": {"alice": {"name": "Alice", "path": "contacts/alice.md", "summary": "", "tags": []}}}
        (tmp_path / "work" / "index.yaml").write_text(yaml.dump(idx))
        (tmp_path / "work" / "contacts" / "alice.md").write_text("Alice")
        (tmp_path / "personal" / "index.yaml").write_text(yaml.dump({}))
        with patch("agent_kit.brain.client._rg_search", return_value=[]):
            results = search_brain(tmp_path, "alice", context="work")
        assert all(r["context"] == "work" for r in results)


# --- _match_weight ---


class TestMatchWeight:
    def test_name_match(self):
        assert _match_weight(["alice"], "Alice Smith", [], "") == 1

    def test_tag_match(self):
        assert _match_weight(["engineer"], "Bob", ["engineer"], "") == 2

    def test_summary_match(self):
        assert _match_weight(["platform"], "Archie", [], "personal AI platform") == 3

    def test_no_match(self):
        assert _match_weight(["xyz"], "Alice", ["friend"], "a contact") is None


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
        result = _extract_metadata(f)
        assert result["name"] == "Test"

    def test_directory_with_readme(self, tmp_path):
        d = tmp_path / "proj"
        d.mkdir()
        (d / "README.md").write_text("---\nname: My Project\n---\nContent")
        assert _extract_metadata(d)["name"] == "My Project"

    def test_directory_without_readme(self, tmp_path):
        d = tmp_path / "proj"
        d.mkdir()
        assert _extract_metadata(d) == {}

    def test_unknown_extension(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert _extract_metadata(f) == {}

    def test_invalid_yaml_file(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("bad: [")
        assert _extract_metadata(f) == {}

    def test_yaml_non_dict(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("- item1\n- item2")
        assert _extract_metadata(f) == {}


# --- _slug_to_name ---


class TestSlugToName:
    def test_hyphens(self):
        assert _slug_to_name("bob-jones") == "Bob Jones"

    def test_underscores(self):
        assert _slug_to_name("bob_jones") == "Bob Jones"


# --- find_project ---


class TestFindProject:
    def test_finds_project(self, tmp_path):
        ctx = tmp_path / "shared"
        proj = ctx / "projects" / "archie"
        proj.mkdir(parents=True)
        (proj / "README.md").write_text("---\nname: Archie\n---\nContent")
        result = find_project(tmp_path, "archie")
        assert result["name"] == "Archie"
        assert result["context"] == "shared"

    def test_not_found(self, tmp_path):
        (tmp_path / "shared").mkdir()
        assert find_project(tmp_path, "nope") is None


# --- file locking ---


class TestContextLock:
    @patch("fcntl.flock")
    def test_lock_acquired_and_released(self, mock_flock, tmp_path):
        """Reindex acquires and releases the lock."""
        ctx = tmp_path / "test"
        for d in ENTITY_DIRS:
            (ctx / d).mkdir(parents=True)
        reindex_context(ctx)
        # flock called at least twice: LOCK_EX and LOCK_UN
        assert mock_flock.call_count >= 2
