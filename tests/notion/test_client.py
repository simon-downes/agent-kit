"""Tests for agent_kit.notion.client — scope checking, ID extraction, and async client functions."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent_kit.errors import ConfigError, ScopeError
from agent_kit.notion.client import (
    _extract_ancestor_ids,
    _in_scope,
    _try_parse_json,
    check_read_scope,
    check_write_scope,
    extract_id,
    fetch_page,
    require_read,
    require_write,
    search,
)
from agent_kit.notion.filters import parse_filter

# --- Sample MCP response text with ancestor XML ---

ANCESTOR_TEXT = (
    '<parent-page url="https://notion.so/Page-abc123def456abc123def456abc123de">'
    "Parent</parent-page>"
    '<ancestor-1-page url="https://notion.so/Root-11111111222233334444555566667777">'
    "Root</ancestor-1-page>"
)


def _mock_session(text_response: str):
    """Create a mock ClientSession that returns text content from call_tool."""
    session = AsyncMock()
    content_block = SimpleNamespace(
        model_dump=lambda: {"type": "text", "text": text_response}
    )
    result = SimpleNamespace(content=[content_block])
    session.call_tool.return_value = result
    return session


# --- Sync helpers ---


class TestRequireRead:
    def test_enabled(self):
        require_read({"notion": {"read": {"enabled": True}}})

    def test_disabled(self):
        with pytest.raises(ConfigError, match="disabled"):
            require_read({"notion": {"read": {"enabled": False}}})

    def test_default_enabled(self):
        require_read({})


class TestRequireWrite:
    def test_enabled(self):
        require_write({"notion": {"write": {"enabled": True}}})

    def test_default_disabled(self):
        with pytest.raises(ConfigError, match="disabled"):
            require_write({})

    def test_disabled(self):
        with pytest.raises(ConfigError, match="disabled"):
            require_write({"notion": {"write": {"enabled": False}}})


class TestExtractAncestorIds:
    def test_extracts_ids(self):
        ids = _extract_ancestor_ids(ANCESTOR_TEXT)
        assert "abc123def456abc123def456abc123de" in ids
        assert "11111111222233334444555566667777" in ids

    def test_no_ancestors(self):
        assert _extract_ancestor_ids("plain text") == []


class TestInScope:
    def test_empty_scope_allows_all(self):
        assert _in_scope({"pages": [], "databases": []}, "any-id", "") is True

    def test_direct_match(self):
        assert _in_scope({"pages": ["abc"], "databases": []}, "abc", "") is True

    def test_ancestor_match(self):
        scope = {"pages": ["abc123def456abc123def456abc123de"], "databases": []}
        assert _in_scope(scope, "other-id", ANCESTOR_TEXT) is True

    def test_no_match(self):
        scope = {"pages": ["not-here"], "databases": []}
        assert _in_scope(scope, "other-id", "no ancestors") is False

    def test_database_scope(self):
        assert _in_scope({"pages": [], "databases": ["db1"]}, "db1", "") is True


class TestCheckScopes:
    def test_read_scope_passes(self):
        config = {"notion": {"read": {"scope": {"pages": ["p1"], "databases": []}}}}
        check_read_scope(config, "p1", "")

    def test_read_scope_fails(self):
        config = {"notion": {"read": {"scope": {"pages": ["p1"], "databases": []}}}}
        with pytest.raises(ScopeError):
            check_read_scope(config, "other", "no ancestors")

    def test_write_scope_passes(self):
        config = {"notion": {"write": {"scope": {"pages": ["p1"], "databases": []}}}}
        check_write_scope(config, "p1", "")

    def test_write_scope_fails(self):
        config = {"notion": {"write": {"scope": {"pages": ["p1"], "databases": []}}}}
        with pytest.raises(ScopeError):
            check_write_scope(config, "other", "no ancestors")


class TestExtractId:
    def test_url(self):
        assert extract_id("https://notion.so/My-Page-abc123") == "abc123"

    def test_url_with_query(self):
        assert extract_id("https://notion.so/Page-abc123?v=1") == "abc123"

    def test_raw_id(self):
        assert extract_id("abc123") == "abc123"

    def test_notion_site_url(self):
        assert extract_id("https://myteam.notion.site/Page-def456") == "def456"


class TestTryParseJson:
    def test_valid_json(self):
        assert _try_parse_json('{"a": 1}') == {"a": 1}

    def test_invalid_json(self):
        assert _try_parse_json("not json") == "not json"


# --- Async client functions ---


class TestFetchPage:
    async def test_returns_parsed_dict(self):
        session = _mock_session('{"title": "My Page", "properties": {"Status": "Done"}}')
        text, parsed = await fetch_page(session, "page-id")
        assert parsed["title"] == "My Page"
        assert "properties" not in parsed  # stripped by default
        session.call_tool.assert_called_once_with("notion-fetch", {"id": "page-id"})

    async def test_with_properties(self):
        session = _mock_session('{"title": "My Page", "properties": {"Status": "Done"}}')
        _, parsed = await fetch_page(session, "page-id", properties=True)
        assert "properties" in parsed


class TestSearch:
    async def test_returns_results(self):
        session = _mock_session('[{"id": "p1", "title": "Result"}]')
        results = await search(session, "test query", limit=5)
        assert len(results) == 1
        assert results[0]["id"] == "p1"
        call_args = session.call_tool.call_args
        assert call_args[0][0] == "notion-search"


# --- Filters ---


class TestParseFilter:
    def test_equals(self):
        assert parse_filter("Status=Done") == ("Status", "=", "Done")

    def test_not_equals(self):
        assert parse_filter("Owner!=Platform") == ("Owner", "!=", "Platform")

    def test_contains(self):
        assert parse_filter("Name~=GitHub") == ("Name", "contains", "GitHub")

    def test_strips_whitespace(self):
        assert parse_filter("Status = Done") == ("Status", "=", "Done")

    def test_invalid(self):
        with pytest.raises(ValueError, match="Invalid filter"):
            parse_filter("no operator here")

    def test_not_equals_before_equals(self):
        """Ensure != is matched before = to avoid splitting on the = in !=."""
        key, op, val = parse_filter("X!=Y")
        assert op == "!="
