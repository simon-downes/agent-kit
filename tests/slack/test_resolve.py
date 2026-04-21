"""Tests for agent_kit.slack.resolve."""

import json
import time

import pytest
import respx
from httpx import Response

from agent_kit.slack.client import SlackClient
from agent_kit.slack.resolve import (
    CACHE_TTL,
    get_channels,
    get_dms,
    get_users,
    resolve_channel,
    resolve_user_name,
    search_users,
)

SLACK_API = "https://slack.com/api"

SAMPLE_CHANNELS = [
    {"id": "C1", "name": "general", "is_private": False, "num_members": 50},
    {"id": "C2", "name": "secret", "is_private": True, "num_members": 5},
]

SAMPLE_DMS = [
    {"id": "D1", "user": "U1", "is_im": True},
    {"id": "G1", "name": "mpdm-a--b-1", "is_mpim": True},
]

SAMPLE_USERS = [
    {
        "id": "U1",
        "name": "alice",
        "real_name": "Alice Smith",
        "profile": {"display_name": "Alice", "email": "alice@co.com"},
    },
    {
        "id": "U2",
        "name": "bob",
        "real_name": "Bob Jones",
        "deleted": True,
        "profile": {"display_name": "Bob"},
    },
    {
        "id": "UBOT",
        "name": "mybot",
        "real_name": "Bot",
        "is_bot": True,
        "profile": {"display_name": "Bot"},
    },
]


@pytest.fixture
def client():
    return SlackClient("xoxp-fake")


class TestFileCache:
    def test_write_and_read(self, cache_dir):
        from agent_kit.slack.resolve import _read_cache, _write_cache

        _write_cache("test", [1, 2, 3])
        assert _read_cache("test") == [1, 2, 3]

    def test_expired_cache_returns_none(self, cache_dir):
        from agent_kit.slack.resolve import _read_cache, _write_cache

        _write_cache("test", [1])
        path = cache_dir / "slack-test.json"
        data = json.loads(path.read_text())
        data["ts"] = time.time() - CACHE_TTL - 1
        path.write_text(json.dumps(data))
        assert _read_cache("test") is None

    def test_corrupt_cache_returns_none(self, cache_dir):
        from agent_kit.slack.resolve import _read_cache

        path = cache_dir / "slack-test.json"
        path.write_text("not json{{{")
        assert _read_cache("test") is None

    def test_missing_cache_returns_none(self, cache_dir):
        from agent_kit.slack.resolve import _read_cache

        assert _read_cache("nonexistent") is None


class TestGetUsers:
    @respx.mock
    def test_fetches_and_filters(self, client, cache_dir):
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": SAMPLE_USERS, "response_metadata": {"next_cursor": ""}},
            )
        )
        users = get_users(client)
        assert "U1" in users
        assert "U2" not in users
        assert "UBOT" not in users

    @respx.mock
    def test_uses_file_cache(self, client, cache_dir):
        route = respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": SAMPLE_USERS, "response_metadata": {"next_cursor": ""}},
            )
        )
        get_users(client)
        get_users(client, no_cache=False)
        assert route.call_count == 1

    @respx.mock
    def test_no_cache_bypasses(self, client, cache_dir):
        route = respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": SAMPLE_USERS, "response_metadata": {"next_cursor": ""}},
            )
        )
        get_users(client)
        get_users(client, no_cache=True)
        assert route.call_count == 2


class TestResolveUserName:
    @respx.mock
    def test_resolves_display_name(self, client, cache_dir):
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": SAMPLE_USERS, "response_metadata": {"next_cursor": ""}},
            )
        )
        assert resolve_user_name(client, "U1") == "Alice"

    @respx.mock
    def test_returns_id_for_unknown(self, client, cache_dir):
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": [], "response_metadata": {"next_cursor": ""}},
            )
        )
        assert resolve_user_name(client, "UUNKNOWN") == "UUNKNOWN"


class TestSearchUsers:
    @respx.mock
    def test_partial_match(self, client, cache_dir):
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": SAMPLE_USERS, "response_metadata": {"next_cursor": ""}},
            )
        )
        results = search_users(client, "ali")
        assert len(results) == 1
        assert results[0]["name"] == "alice"


class TestGetChannels:
    @respx.mock
    def test_fetches_channels(self, client, cache_dir):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": SAMPLE_CHANNELS,
                    "response_metadata": {"next_cursor": ""},
                },
            )
        )
        chs = get_channels(client)
        assert len(chs) == 2

    @respx.mock
    def test_caches_to_file(self, client, cache_dir):
        route = respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": SAMPLE_CHANNELS,
                    "response_metadata": {"next_cursor": ""},
                },
            )
        )
        get_channels(client)
        get_channels(client)
        assert route.call_count == 1


class TestGetDms:
    @respx.mock
    def test_filters_group_dms_by_default(self, client, cache_dir):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": SAMPLE_DMS,
                    "response_metadata": {"next_cursor": ""},
                },
            )
        )
        dms_list = get_dms(client)
        assert len(dms_list) == 1
        assert dms_list[0]["id"] == "D1"

    @respx.mock
    def test_includes_group_dms(self, client, cache_dir):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": SAMPLE_DMS,
                    "response_metadata": {"next_cursor": ""},
                },
            )
        )
        dms_list = get_dms(client, include_group=True)
        assert len(dms_list) == 2


class TestResolveChannel:
    @respx.mock
    def test_hash_name(self, client, cache_dir):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": SAMPLE_CHANNELS,
                    "response_metadata": {"next_cursor": ""},
                },
            )
        )
        channel_id, ch_type = resolve_channel(client, "#general")
        assert channel_id == "C1"
        assert ch_type == "public"

    @respx.mock
    def test_hash_name_not_found(self, client, cache_dir):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "channels": [], "response_metadata": {"next_cursor": ""}},
            )
        )
        with pytest.raises(ValueError, match="not found"):
            resolve_channel(client, "#nonexistent")

    @respx.mock
    def test_at_user(self, client, cache_dir):
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": SAMPLE_USERS, "response_metadata": {"next_cursor": ""}},
            )
        )
        respx.post(f"{SLACK_API}/conversations.open").mock(
            return_value=Response(200, json={"ok": True, "channel": {"id": "D99"}})
        )
        channel_id, ch_type = resolve_channel(client, "@alice")
        assert channel_id == "D99"
        assert ch_type == "im"

    @respx.mock
    def test_raw_id_from_channels(self, client, cache_dir):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": SAMPLE_CHANNELS,
                    "response_metadata": {"next_cursor": ""},
                },
            )
        )
        channel_id, ch_type = resolve_channel(client, "C2")
        assert channel_id == "C2"
        assert ch_type == "private"

    @respx.mock
    def test_raw_id_not_found_returns_fallback(self, client, cache_dir):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "channels": [], "response_metadata": {"next_cursor": ""}},
            )
        )
        channel_id, ch_type = resolve_channel(client, "CUNKNOWN")
        assert channel_id == "CUNKNOWN"
        assert ch_type is None
