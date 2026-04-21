"""Tests for agent_kit.slack.cli."""

import json
from unittest.mock import patch

import respx
from httpx import Response

from agent_kit.slack.cli import slack
from agent_kit.slack.client import SlackClient

SLACK_API = "https://slack.com/api"

CHANNELS_RESPONSE = {
    "ok": True,
    "channels": [
        {"id": "C1", "name": "general", "is_private": False, "num_members": 50},
        {"id": "C2", "name": "secret", "is_private": True, "num_members": 5},
    ],
    "response_metadata": {"next_cursor": ""},
}

DMS_RESPONSE = {
    "ok": True,
    "channels": [
        {"id": "D1", "user": "U1", "is_im": True},
        {"id": "G1", "name": "mpdm-a--b-1", "is_mpim": True},
    ],
    "response_metadata": {"next_cursor": ""},
}

USERS_RESPONSE = {
    "ok": True,
    "members": [
        {
            "id": "U1",
            "name": "alice",
            "real_name": "Alice",
            "profile": {"display_name": "Alice", "email": "a@co.com"},
        },
    ],
    "response_metadata": {"next_cursor": ""},
}

HISTORY_RESPONSE = {
    "ok": True,
    "messages": [
        {"ts": "1.0", "user": "U1", "text": "hello", "reply_count": 0},
    ],
    "response_metadata": {"next_cursor": ""},
}

SEARCH_RESPONSE = {
    "ok": True,
    "messages": {
        "matches": [
            {
                "channel": {"name": "general"},
                "ts": "1.0",
                "user": "U1",
                "text": "deploy done",
                "permalink": "https://slack.com/p1",
            },
        ],
    },
}


def _mock_client():
    """Patch _get_client to return a real SlackClient with a fake token."""
    client = SlackClient("xoxp-fake", webhook_url="https://hooks.slack.com/test")
    return patch("agent_kit.slack.cli._get_client", return_value=client)


class TestChannelsCommand:
    @respx.mock
    def test_lists_channels(self, cli_runner, mock_config, cache_dir):
        mock_config()
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(200, json=CHANNELS_RESPONSE)
        )
        with _mock_client():
            result = cli_runner.invoke(slack, ["channels"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["name"] == "general"
        assert data[0]["type"] == "public"
        assert data[1]["type"] == "private"

    @respx.mock
    def test_limit(self, cli_runner, mock_config, cache_dir):
        mock_config()
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(200, json=CHANNELS_RESPONSE)
        )
        with _mock_client():
            result = cli_runner.invoke(slack, ["channels", "--limit", "1"])
        data = json.loads(result.output)
        assert len(data) == 1


class TestDmsCommand:
    @respx.mock
    def test_lists_dms(self, cli_runner, mock_config, cache_dir):
        mock_config()
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(200, json=DMS_RESPONSE)
        )
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(200, json=USERS_RESPONSE)
        )
        with _mock_client():
            result = cli_runner.invoke(slack, ["dms"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["type"] == "dm"

    @respx.mock
    def test_group_flag(self, cli_runner, mock_config, cache_dir):
        mock_config()
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(200, json=DMS_RESPONSE)
        )
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(200, json=USERS_RESPONSE)
        )
        with _mock_client():
            result = cli_runner.invoke(slack, ["dms", "--group"])
        data = json.loads(result.output)
        assert len(data) == 2


class TestHistoryCommand:
    @respx.mock
    def test_reads_history(self, cli_runner, mock_config, cache_dir):
        mock_config()
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(200, json=CHANNELS_RESPONSE)
        )
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(200, json=USERS_RESPONSE)
        )
        respx.get(f"{SLACK_API}/conversations.history").mock(
            return_value=Response(200, json=HISTORY_RESPONSE)
        )
        with _mock_client():
            result = cli_runner.invoke(slack, ["history", "#general", "--limit", "5"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["user"] == "Alice"


class TestThreadCommand:
    @respx.mock
    def test_reads_thread(self, cli_runner, mock_config, cache_dir):
        mock_config()
        respx.get(f"{SLACK_API}/conversations.list").mock(
            return_value=Response(200, json=CHANNELS_RESPONSE)
        )
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(200, json=USERS_RESPONSE)
        )
        respx.get(f"{SLACK_API}/conversations.replies").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "messages": [{"ts": "1.0", "user": "U1", "text": "reply"}],
                    "response_metadata": {"next_cursor": ""},
                },
            )
        )
        with _mock_client():
            result = cli_runner.invoke(slack, ["thread", "#general", "1.0"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["text"] == "reply"


class TestSearchCommand:
    @respx.mock
    def test_searches(self, cli_runner, mock_config, cache_dir):
        mock_config()
        respx.get(f"{SLACK_API}/search.messages").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(200, json=USERS_RESPONSE)
        )
        with _mock_client():
            result = cli_runner.invoke(slack, ["search", "deploy"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["channel"] == "general"


class TestUsersCommand:
    @respx.mock
    def test_lists_users(self, cli_runner, mock_config, cache_dir):
        mock_config()
        respx.get(f"{SLACK_API}/users.list").mock(
            return_value=Response(200, json=USERS_RESPONSE)
        )
        with _mock_client():
            result = cli_runner.invoke(slack, ["users"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["name"] == "alice"


class TestSendCommand:
    @respx.mock
    def test_sends_webhook(self, cli_runner):
        respx.post("https://hooks.slack.com/test").mock(
            return_value=Response(200, text="ok")
        )
        with _mock_client():
            result = cli_runner.invoke(slack, ["send", "hello world"])
        assert result.exit_code == 0
        assert "OK" in result.output
