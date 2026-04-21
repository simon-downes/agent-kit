"""Tests for agent_kit.slack.client.SlackClient."""

from unittest.mock import patch

import httpx
import pytest
import respx
from httpx import Response

from agent_kit.errors import AuthError
from agent_kit.slack.client import SlackClient

SLACK_API = "https://slack.com/api"


class TestGet:
    @respx.mock
    def test_returns_json(self):
        respx.get(f"{SLACK_API}/auth.test").mock(
            return_value=Response(200, json={"ok": True, "user": "U123"})
        )
        client = SlackClient("xoxp-fake")
        result = client._get("auth.test")
        assert result["user"] == "U123"

    @respx.mock
    def test_raises_on_not_ok(self):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(200, json={"ok": False, "error": "missing_scope"})
        )
        client = SlackClient("xoxp-fake")
        with pytest.raises(ValueError, match="missing_scope"):
            client._get("conversations.list")

    @respx.mock
    def test_raises_auth_error_on_token_revoked(self):
        respx.get(f"{SLACK_API}/auth.test").mock(
            return_value=Response(200, json={"ok": False, "error": "token_revoked"})
        )
        client = SlackClient("xoxp-fake")
        with pytest.raises(AuthError, match="token_revoked"):
            client._get("auth.test")

    @respx.mock
    def test_raises_on_429_with_retry_after(self):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                429,
                headers={"Retry-After": "30"},
                json={"ok": False, "error": "ratelimited"},
            )
        )
        client = SlackClient("xoxp-fake")
        with pytest.raises(httpx.HTTPStatusError, match="retry after 30s"):
            client._get("conversations.list")


class TestPost:
    @respx.mock
    def test_sends_post(self):
        route = respx.post(f"{SLACK_API}/conversations.open").mock(
            return_value=Response(200, json={"ok": True, "channel": {"id": "D123"}})
        )
        client = SlackClient("xoxp-fake")
        result = client._post("conversations.open", {"users": "U456"})
        assert result["channel"]["id"] == "D123"
        assert route.calls[0].request.method == "POST"


class TestPaginatedGet:
    @respx.mock
    def test_single_page(self):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": [{"id": "C1"}, {"id": "C2"}],
                    "response_metadata": {"next_cursor": ""},
                },
            )
        )
        client = SlackClient("xoxp-fake")
        result = client._paginated_get("conversations.list", "channels", limit=10)
        assert len(result) == 2

    @respx.mock
    def test_respects_limit(self):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": [{"id": f"C{i}"} for i in range(200)],
                    "response_metadata": {"next_cursor": "abc"},
                },
            )
        )
        client = SlackClient("xoxp-fake")
        result = client._paginated_get("conversations.list", "channels", limit=5)
        assert len(result) == 5

    @respx.mock
    def test_stops_on_empty_page(self):
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": [], "response_metadata": {"next_cursor": "abc"}},
            )
        )
        client = SlackClient("xoxp-fake")
        result = client._paginated_get("users.list", "members", limit=100)
        assert result == []

    @respx.mock
    def test_multi_page(self):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "ok": True,
                        "channels": [{"id": "C1"}],
                        "response_metadata": {"next_cursor": "page2"},
                    },
                ),
                Response(
                    200,
                    json={
                        "ok": True,
                        "channels": [{"id": "C2"}],
                        "response_metadata": {"next_cursor": ""},
                    },
                ),
            ]
        )
        client = SlackClient("xoxp-fake")
        with patch("agent_kit.slack.client.time.sleep"):
            result = client._paginated_get("conversations.list", "channels", limit=10)
        assert [c["id"] for c in result] == ["C1", "C2"]

    @respx.mock
    def test_max_pages_guard(self, capsys):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": [{"id": "C1"}],
                    "response_metadata": {"next_cursor": "more"},
                },
            )
        )
        client = SlackClient("xoxp-fake")
        with patch("agent_kit.slack.client.time.sleep"):
            result = client._paginated_get("conversations.list", "channels", limit=9999)
        assert len(result) == 10
        assert "max page limit" in capsys.readouterr().err


class TestPublicMethods:
    @respx.mock
    def test_get_channels(self):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": [{"id": "C1", "name": "general"}],
                    "response_metadata": {"next_cursor": ""},
                },
            )
        )
        client = SlackClient("xoxp-fake")
        chs = client.get_channels()
        assert chs[0]["name"] == "general"

    @respx.mock
    def test_search_messages(self):
        respx.get(f"{SLACK_API}/search.messages").mock(
            return_value=Response(
                200, json={"ok": True, "messages": {"matches": [{"text": "hello"}]}}
            )
        )
        client = SlackClient("xoxp-fake")
        data = client.search_messages("hello")
        assert data["messages"]["matches"][0]["text"] == "hello"

    @respx.mock
    def test_open_conversation(self):
        respx.post(f"{SLACK_API}/conversations.open").mock(
            return_value=Response(200, json={"ok": True, "channel": {"id": "D1"}})
        )
        client = SlackClient("xoxp-fake")
        result = client.open_conversation("U1")
        assert result["channel"]["id"] == "D1"


class TestWebhook:
    @respx.mock
    def test_send_webhook(self):
        route = respx.post("https://hooks.slack.com/test").mock(
            return_value=Response(200, text="ok")
        )
        client = SlackClient("xoxp-fake", webhook_url="https://hooks.slack.com/test")
        client.send_webhook("hello")
        assert route.called

    def test_send_webhook_no_url(self):
        client = SlackClient("xoxp-fake")
        with pytest.raises(AuthError, match="webhook"):
            client.send_webhook("hello")


class TestRequireReadAndScope:
    """Test the CLI-level config checks (moved from api.py)."""

    def test_require_read_enabled(self):
        from agent_kit.slack.cli import _require_read

        _require_read({"slack": {"read": {"enabled": True}}})

    def test_require_read_disabled(self):
        from agent_kit.slack.cli import _require_read

        with pytest.raises(Exception, match="disabled"):
            _require_read({"slack": {"read": {"enabled": False}}})

    def test_require_read_default(self):
        from agent_kit.slack.cli import _require_read

        _require_read({})

    def test_scope_dm_disabled(self):
        from agent_kit.slack.cli import _check_channel_scope

        config = {"slack": {"read": {"scope": {"include_dms": False}}}}
        with pytest.raises(Exception, match="DM"):
            _check_channel_scope(config, "D1", "im")

    def test_scope_group_dm_disabled(self):
        from agent_kit.slack.cli import _check_channel_scope

        config = {"slack": {"read": {"scope": {"include_group_dms": False}}}}
        with pytest.raises(Exception, match="Group DM"):
            _check_channel_scope(config, "G1", "mpim")

    def test_scope_channel_not_allowed(self):
        from agent_kit.slack.cli import _check_channel_scope

        config = {"slack": {"read": {"scope": {"channels": ["#general"]}}}}
        with pytest.raises(Exception, match="not in"):
            _check_channel_scope(config, "C999", None)

    def test_scope_channel_allowed(self):
        from agent_kit.slack.cli import _check_channel_scope

        config = {"slack": {"read": {"scope": {"channels": ["#general"]}}}}
        _check_channel_scope(config, "#general", None)

    def test_scope_empty_allows_all(self):
        from agent_kit.slack.cli import _check_channel_scope

        config = {"slack": {"read": {"scope": {"channels": []}}}}
        _check_channel_scope(config, "C999", None)
