"""Tests for agent_kit.slack.api."""

from unittest.mock import patch

import httpx
import pytest
import respx
from httpx import Response

from agent_kit.errors import AuthError, ConfigError
from agent_kit.slack.api import api_get, api_post, check_channel_scope, paginated_get, require_read

SLACK_API = "https://slack.com/api"


@pytest.fixture(autouse=True)
def _fake_token():
    with patch("agent_kit.slack.api.get_user_token", return_value="xoxp-fake"):
        yield


class TestApiGet:
    @respx.mock
    def test_returns_json(self):
        respx.get(f"{SLACK_API}/auth.test").mock(
            return_value=Response(200, json={"ok": True, "user": "U123"})
        )
        result = api_get("auth.test")
        assert result["user"] == "U123"

    @respx.mock
    def test_raises_on_not_ok(self):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(200, json={"ok": False, "error": "missing_scope"})
        )
        with pytest.raises(ValueError, match="missing_scope"):
            api_get("conversations.list")

    @respx.mock
    def test_raises_auth_error_on_token_revoked(self):
        respx.get(f"{SLACK_API}/auth.test").mock(
            return_value=Response(200, json={"ok": False, "error": "token_revoked"})
        )
        with pytest.raises(AuthError, match="token_revoked"):
            api_get("auth.test")

    @respx.mock
    def test_clears_cached_token_on_auth_error(self):
        import agent_kit.slack.api as mod

        mod._cached_token = "old"
        respx.get(f"{SLACK_API}/auth.test").mock(
            return_value=Response(200, json={"ok": False, "error": "invalid_auth"})
        )
        with pytest.raises(AuthError):
            api_get("auth.test")
        assert mod._cached_token is None

    @respx.mock
    def test_raises_on_429_with_retry_after(self):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                429,
                headers={"Retry-After": "30"},
                json={"ok": False, "error": "ratelimited"},
            )
        )
        with pytest.raises(httpx.HTTPStatusError, match="retry after 30s"):
            api_get("conversations.list")


class TestApiPost:
    @respx.mock
    def test_sends_post(self):
        route = respx.post(f"{SLACK_API}/conversations.open").mock(
            return_value=Response(200, json={"ok": True, "channel": {"id": "D123"}})
        )
        result = api_post("conversations.open", {"users": "U456"})
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
        result = paginated_get("conversations.list", "channels", limit=10)
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
        result = paginated_get("conversations.list", "channels", limit=5)
        assert len(result) == 5

    @respx.mock
    def test_stops_on_empty_page(self):
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": [], "response_metadata": {"next_cursor": "abc"}},
            )
        )
        result = paginated_get("users.list", "members", limit=100)
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
        with patch("agent_kit.slack.api.time.sleep"):
            result = paginated_get("conversations.list", "channels", limit=10)
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
        with patch("agent_kit.slack.api.time.sleep"):
            result = paginated_get("conversations.list", "channels", limit=9999)
        assert len(result) == 10  # max_pages=10, 1 item per page
        assert "max page limit" in capsys.readouterr().err


class TestRequireRead:
    def test_passes_when_enabled(self):
        require_read({"slack": {"read": {"enabled": True}}})

    def test_passes_when_missing(self):
        require_read({})

    def test_raises_when_disabled(self):
        with pytest.raises(ConfigError, match="disabled"):
            require_read({"slack": {"read": {"enabled": False}}})


class TestCheckChannelScope:
    def test_dm_disabled(self):
        config = {"slack": {"read": {"scope": {"include_dms": False}}}}
        with pytest.raises(ConfigError, match="DM access"):
            check_channel_scope(config, "D1", "im")

    def test_group_dm_disabled(self):
        config = {"slack": {"read": {"scope": {"include_group_dms": False}}}}
        with pytest.raises(ConfigError, match="Group DM"):
            check_channel_scope(config, "G1", "mpim")

    def test_channel_not_in_allowed_list(self):
        config = {"slack": {"read": {"scope": {"channels": ["C1", "C2"]}}}}
        with pytest.raises(ConfigError, match="not in the configured scope"):
            check_channel_scope(config, "C99", "public")

    def test_passes_when_in_allowed_list(self):
        config = {"slack": {"read": {"scope": {"channels": ["C1"]}}}}
        check_channel_scope(config, "C1", "public")

    def test_passes_when_no_scope(self):
        check_channel_scope({}, "C1", "public")