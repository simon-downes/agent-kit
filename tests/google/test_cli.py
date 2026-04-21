"""Tests for agent_kit.google.cli."""

import json
from unittest.mock import patch

import respx
from httpx import Response

from agent_kit.google.cli import google

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
CAL_API = "https://www.googleapis.com/calendar/v3"
DRIVE_API = "https://www.googleapis.com/drive/v3"

SAMPLE_EVENT = {
    "id": "ev1",
    "summary": "Standup",
    "start": {"dateTime": "2026-01-01T09:00:00Z"},
    "end": {"dateTime": "2026-01-01T09:30:00Z"},
    "status": "confirmed",
}

SAMPLE_FILE = {
    "id": "f1",
    "name": "My Doc",
    "mimeType": "application/pdf",
    "modifiedTime": "2026-01-01T00:00:00Z",
    "owners": [{"emailAddress": "a@co.com"}],
}


class TestMailSearch:
    @respx.mock
    def test_search(self, cli_runner):
        with patch("agent_kit.google.cli.require_service"):
            respx.get(f"{GMAIL_API}/messages").mock(
                return_value=Response(200, json={"messages": []})
            )
            result = cli_runner.invoke(google, ["mail", "search", "test"])
            assert result.exit_code == 0
            assert json.loads(result.output) == []


class TestMailRecent:
    @respx.mock
    def test_recent(self, cli_runner):
        with patch("agent_kit.google.cli.require_service"):
            respx.get(f"{GMAIL_API}/messages").mock(
                return_value=Response(200, json={"messages": []})
            )
            result = cli_runner.invoke(google, ["mail", "recent"])
            assert result.exit_code == 0


class TestMailUnread:
    @respx.mock
    def test_unread(self, cli_runner):
        with patch("agent_kit.google.cli.require_service"):
            respx.get(f"{GMAIL_API}/messages").mock(
                return_value=Response(200, json={"messages": []})
            )
            result = cli_runner.invoke(google, ["mail", "unread"])
            assert result.exit_code == 0


class TestCalendarToday:
    @respx.mock
    def test_today(self, cli_runner):
        with patch("agent_kit.google.cli.require_service"):
            respx.get(f"{CAL_API}/calendars/primary/events").mock(
                return_value=Response(200, json={"items": [SAMPLE_EVENT]})
            )
            result = cli_runner.invoke(google, ["calendar", "today"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert len(data) == 1
            assert data[0]["summary"] == "Standup"


class TestCalendarUpcoming:
    @respx.mock
    def test_upcoming(self, cli_runner):
        with patch("agent_kit.google.cli.require_service"):
            respx.get(f"{CAL_API}/calendars/primary/events").mock(
                return_value=Response(200, json={"items": []})
            )
            result = cli_runner.invoke(google, ["calendar", "upcoming"])
            assert result.exit_code == 0


class TestCalendarEvent:
    @respx.mock
    def test_event(self, cli_runner):
        with patch("agent_kit.google.cli.require_service"):
            respx.get(f"{CAL_API}/calendars/primary/events/ev1").mock(
                return_value=Response(200, json=SAMPLE_EVENT)
            )
            result = cli_runner.invoke(google, ["calendar", "event", "ev1"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["id"] == "ev1"


class TestDriveSearch:
    @respx.mock
    def test_search(self, cli_runner):
        with patch("agent_kit.google.cli.require_service"):
            respx.get(f"{DRIVE_API}/files").mock(
                return_value=Response(200, json={"files": [SAMPLE_FILE]})
            )
            result = cli_runner.invoke(google, ["drive", "search", "doc"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data[0]["name"] == "My Doc"


class TestDriveRecent:
    @respx.mock
    def test_recent(self, cli_runner):
        with patch("agent_kit.google.cli.require_service"):
            respx.get(f"{DRIVE_API}/files").mock(
                return_value=Response(200, json={"files": []})
            )
            result = cli_runner.invoke(google, ["drive", "recent"])
            assert result.exit_code == 0


class TestDriveList:
    @respx.mock
    def test_list(self, cli_runner):
        with patch("agent_kit.google.cli.require_service"):
            respx.get(f"{DRIVE_API}/files").mock(
                return_value=Response(200, json={"files": []})
            )
            result = cli_runner.invoke(google, ["drive", "list"])
            assert result.exit_code == 0
