"""Tests for agent_kit.slack.resolve."""

import json
import time
from unittest.mock import patch

import pytest
import respx
from httpx import Response

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


@pytest.fixture(autouse=True)
def _fake_token():
    with patch("agent_kit.slack.api.get_user_token", return_value="xoxp-fake"):
        yield


class TestFileCache:
    def test_write_and_read(self, cache_dir):
        from agent_kit.slack.resolve import _read_cache, _write_cache

        _write_cache("test", [1, 2, 3])
        assert _read_cache("test") == [1, 2, 3]

    def test_expired_cache_returns_none(self, cache_dir):
        from agent_kit.slack.resolve import _read_cache, _write_cache

        _write_cache("test", [1])
        # Backdate the timestamp
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
    def test_fetches_and_filters(self, cache_dir):
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": SAMPLE_USERS, "response_metadata": {"next_cursor": ""}},
            )
        )
        users = get_users()
        assert "U1" in users  # active user
        assert "U2" not in users  # deleted
        assert "UBOT" not in users  # bot

    @respx.mock
    def test_uses_file_cache(self, cache_dir):
        route = respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": SAMPLE_USERS, "response_metadata": {"next_cursor": ""}},
            )
        )
        get_users()
        get_users(no_cache=False)  # should hit cache
        assert route.call_count == 1

    @respx.mock
    def test_no_cache_bypasses(self, cache_dir):
        route = respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": SAMPLE_USERS, "response_metadata": {"next_cursor": ""}},
            )
        )
        get_users()
        get_users(no_cache=True)
        assert route.call_count == 2


class TestResolveUserName:
    @respx.mock
    def test_resolves_display_name(self, cache_dir):
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": SAMPLE_USERS, "response_metadata": {"next_cursor": ""}},
            )
        )
        assert resolve_user_name("U1") == "Alice"

    @respx.mock
    def test_returns_id_for_unknown(self, cache_dir):
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": [], "response_metadata": {"next_cursor": ""}},
            )
        )
        assert resolve_user_name("UUNKNOWN") == "UUNKNOWN"


class TestSearchUsers:
    @respx.mock
    def test_partial_match(self, cache_dir):
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": SAMPLE_USERS, "response_metadata": {"next_cursor": ""}},
            )
        )
        results = search_users("ali")
        assert len(results) == 1
        assert results[0]["name"] == "alice"


class TestGetChannels:
    @respx.mock
    def test_fetches_channels(self, cache_dir):
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
        chs = get_channels()
        assert len(chs) == 2

    @respx.mock
    def test_caches_to_file(self, cache_dir):
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
        get_channels()
        get_channels()
        assert route.call_count == 1


class TestGetDms:
    @respx.mock
    def test_filters_group_dms_by_default(self, cache_dir):
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
        dms = get_dms()
        assert len(dms) == 1
        assert dms[0]["id"] == "D1"

    @respx.mock
    def test_includes_group_dms(self, cache_dir):
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
        dms = get_dms(include_group=True)
        assert len(dms) == 2


class TestResolveChannel:
    @respx.mock
    def test_hash_name(self, cache_dir):
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
        channel_id, ch_type = resolve_channel("#general")
        assert channel_id == "C1"
        assert ch_type == "public"

    @respx.mock
    def test_hash_name_not_found(self, cache_dir):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "channels": [], "response_metadata": {"next_cursor": ""}},
            )
        )
        with pytest.raises(ValueError, match="not found"):
            resolve_channel("#nonexistent")

    @respx.mock
    def test_at_user(self, cache_dir):
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(
                200,
                json={"ok": True, "members": SAMPLE_USERS, "response_metadata": {"next_cursor": ""}},
            )
        )
        respx.post(f"{SLACK_API}/conversations.open").mock(
            return_value=Response(200, json={"ok": True, "channel": {"id": "D99"}})
        )
        channel_id, ch_type = resolve_channel("@alice")
        assert channel_id == "D99"
        assert ch_type == "im"

    @respx.mock
    def test_raw_id_from_channels(self, cache_dir):
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
        channel_id, ch_type = resolve_channel("C2")
        assert channel_id == "C2"
        assert ch_type == "private"

    @respx.mock
    def test_raw_id_not_found_returns_fallback(self, cache_dir):
        respx.get(f"{SLACK_API}/conversations.list").mock(
            side_effect=[
                Response(
                    200,
                    json={"ok": True, "channels": [], "response_metadata": {"next_cursor": ""}},
                ),
                Response(
                    200,
                    json={"ok": True, "channels": [], "response_metadata": {"next_cursor": ""}},
                ),
            ]
        )
        channel_id, ch_type = resolve_channel("CUNKNOWN")
        assert channel_id == "CUNKNOWN"
        assert ch_type is None
