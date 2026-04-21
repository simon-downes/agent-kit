"""Tests for agent_kit.notion.cli."""

import json
from unittest.mock import AsyncMock, patch

from agent_kit.notion.cli import notion


def _patch_notion_session():
    """Patch _session to return a mock async context manager."""
    session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return patch("agent_kit.notion.cli._session", return_value=ctx), session


class TestSearchCommand:
    def test_search(self, cli_runner, mock_config):
        mock_config()
        session_patch, session = _patch_notion_session()
        with (
            session_patch,
            patch("agent_kit.notion.cli._get_token", return_value="fake-token"),
            patch(
                "agent_kit.notion.cli.search",
                return_value=[{"id": "p1", "title": "Result"}],
            ),
        ):
            result = cli_runner.invoke(notion, ["search", "test"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["title"] == "Result"


class TestPageCommand:
    def test_fetch_page(self, cli_runner, mock_config):
        mock_config()
        session_patch, session = _patch_notion_session()
        with (
            session_patch,
            patch("agent_kit.notion.cli._get_token", return_value="fake-token"),
            patch(
                "agent_kit.notion.cli.fetch_page",
                return_value=("raw text", {"title": "My Page"}),
            ),
            patch("agent_kit.notion.cli.check_read_scope"),
        ):
            result = cli_runner.invoke(notion, ["page", "abc123"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["title"] == "My Page"

    def test_fetch_page_markdown(self, cli_runner, mock_config):
        mock_config()
        session_patch, session = _patch_notion_session()
        with (
            session_patch,
            patch("agent_kit.notion.cli._get_token", return_value="fake-token"),
            patch(
                "agent_kit.notion.cli.fetch_page",
                return_value=("raw", {"content": "# Hello"}),
            ),
            patch("agent_kit.notion.cli.check_read_scope"),
        ):
            result = cli_runner.invoke(notion, ["page", "abc123", "--markdown"])
        assert result.exit_code == 0
        assert "# Hello" in result.output


class TestCommentsCommand:
    def test_fetch_comments(self, cli_runner, mock_config):
        mock_config()
        session_patch, session = _patch_notion_session()
        with (
            session_patch,
            patch("agent_kit.notion.cli._get_token", return_value="fake-token"),
            patch(
                "agent_kit.notion.cli.fetch_comments",
                return_value=[{"author": "Alice", "text": "LGTM"}],
            ),
            patch("agent_kit.notion.cli.check_read_scope"),
            patch("agent_kit.notion.cli.fetch_page", return_value=("raw", {})),
        ):
            result = cli_runner.invoke(notion, ["comments", "abc123"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["author"] == "Alice"
