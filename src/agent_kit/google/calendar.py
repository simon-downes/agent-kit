"""Google Calendar API client."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from agent_kit.google.auth import get_token

API_BASE = "https://www.googleapis.com/calendar/v3"


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    token = get_token()
    resp = httpx.get(
        f"{API_BASE}{path}",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code == 401:
        from agent_kit.google.auth import _refresh

        token = _refresh()
        resp = httpx.get(
            f"{API_BASE}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    if resp.status_code in (401, 403):
        resp.raise_for_status()
    if resp.status_code == 429:
        raise httpx.HTTPStatusError(
            "Google API rate limit exceeded, try again later",
            request=resp.request,
            response=resp,
        )
    if resp.status_code >= 400:
        _raise_error(resp)
    return resp.json()


def _raise_error(resp: httpx.Response) -> None:
    try:
        body = resp.json()
        msg = body.get("error", {}).get("message", "")
    except Exception:
        msg = ""
    if msg:
        raise ValueError(msg)
    resp.raise_for_status()


def _format_event(event: dict[str, Any]) -> dict[str, Any]:
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event.get("id"),
        "summary": event.get("summary", "(no title)"),
        "start": start.get("dateTime", start.get("date")),
        "end": end.get("dateTime", end.get("date")),
        "attendees": [a.get("email") for a in event.get("attendees", []) if a.get("email")],
        "meetLink": event.get("hangoutLink"),
        "status": event.get("status"),
    }


def _format_event_detail(event: dict[str, Any]) -> dict[str, Any]:
    result = _format_event(event)
    result["description"] = event.get("description")
    result["organizer"] = (event.get("organizer") or {}).get("email")
    result["location"] = event.get("location")
    return result


def get_events(*, time_min: str, time_max: str, limit: int = 50) -> list[dict[str, Any]]:
    data = _get(
        "/calendars/primary/events",
        params={
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": limit,
        },
    )
    return [_format_event(e) for e in data.get("items", [])]


def get_today() -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return get_events(time_min=start.isoformat(), time_max=end.isoformat())


def get_upcoming(days: int = 7) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    end = now + timedelta(days=days)
    return get_events(time_min=now.isoformat(), time_max=end.isoformat())


def get_event(event_id: str) -> dict[str, Any]:
    data = _get(f"/calendars/primary/events/{event_id}")
    return _format_event_detail(data)
