"""Tests for agent_kit.google.calendar."""

import respx
from httpx import Response

from agent_kit.google.calendar import _format_event, _format_event_detail, get_event, get_events

CAL_API = "https://www.googleapis.com/calendar/v3"

SAMPLE_EVENT = {
    "id": "ev1",
    "summary": "Standup",
    "start": {"dateTime": "2026-01-01T09:00:00Z"},
    "end": {"dateTime": "2026-01-01T09:30:00Z"},
    "attendees": [{"email": "a@co.com"}, {"email": "b@co.com"}],
    "hangoutLink": "https://meet.google.com/abc",
    "status": "confirmed",
    "description": "Daily standup",
    "organizer": {"email": "a@co.com"},
    "location": "Room 1",
}


class TestFormatEvent:
    def test_formats_event(self):
        result = _format_event(SAMPLE_EVENT)
        assert result["id"] == "ev1"
        assert result["summary"] == "Standup"
        assert result["start"] == "2026-01-01T09:00:00Z"
        assert result["attendees"] == ["a@co.com", "b@co.com"]
        assert result["meetLink"] == "https://meet.google.com/abc"

    def test_all_day_event(self):
        event = {"id": "ev2", "start": {"date": "2026-01-01"}, "end": {"date": "2026-01-02"}}
        result = _format_event(event)
        assert result["start"] == "2026-01-01"
        assert result["summary"] == "(no title)"

    def test_no_attendees(self):
        event = {"id": "ev3", "start": {}, "end": {}}
        result = _format_event(event)
        assert result["attendees"] == []


class TestFormatEventDetail:
    def test_includes_extra_fields(self):
        result = _format_event_detail(SAMPLE_EVENT)
        assert result["description"] == "Daily standup"
        assert result["organizer"] == "a@co.com"
        assert result["location"] == "Room 1"


class TestGetEvents:
    @respx.mock
    def test_fetches_events(self):
        respx.get(f"{CAL_API}/calendars/primary/events").mock(
            return_value=Response(200, json={"items": [SAMPLE_EVENT]})
        )
        result = get_events(
            time_min="2026-01-01T00:00:00Z",
            time_max="2026-01-02T00:00:00Z",
        )
        assert len(result) == 1
        assert result[0]["summary"] == "Standup"


class TestGetEvent:
    @respx.mock
    def test_fetches_single_event(self):
        respx.get(f"{CAL_API}/calendars/primary/events/ev1").mock(
            return_value=Response(200, json=SAMPLE_EVENT)
        )
        result = get_event("ev1")
        assert result["id"] == "ev1"
        assert result["description"] == "Daily standup"
