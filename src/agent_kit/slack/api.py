"""Slack Web API client for read operations."""

import sys
import time
from typing import Any

import httpx

from agent_kit.errors import AuthError, ConfigError

API_BASE = "https://slack.com/api"

_cached_token: str | None = None


def get_user_token() -> str:
    """Get a valid Slack user token."""
    global _cached_token
    if _cached_token:
        return _cached_token

    from agent_kit.auth import get_field

    token = get_field("slack", "access_token")
    if not token:
        raise AuthError("no Slack user token — run 'ak auth login slack'")

    _cached_token = token
    return token


def require_read(config: dict) -> None:
    """Check that Slack read is enabled."""
    if not config.get("slack", {}).get("read", {}).get("enabled", True):
        raise ConfigError("Slack read operations are disabled in config")


def check_channel_scope(config: dict, channel_id: str, channel_type: str | None = None) -> None:
    """Check if a channel is within the configured scope."""
    scope = config.get("slack", {}).get("read", {}).get("scope", {})

    if channel_type == "im" and not scope.get("include_dms", False):
        raise ConfigError("DM access is disabled in config (set slack.read.scope.include_dms)")
    if channel_type == "mpim" and not scope.get("include_group_dms", False):
        raise ConfigError(
            "Group DM access is disabled in config (set slack.read.scope.include_group_dms)"
        )

    allowed = scope.get("channels", [])
    if allowed and channel_id not in allowed and f"#{channel_id}" not in allowed:
        raise ConfigError(f"channel {channel_id} is not in the configured scope")


def _call(method: str, *, post: bool = False, params: dict[str, Any] | None = None) -> dict:
    """Call a Slack Web API method (GET or POST)."""
    global _cached_token
    token = get_user_token()
    headers = {"Authorization": f"Bearer {token}"}

    if post:
        resp = httpx.post(f"{API_BASE}/{method}", data=params or {}, headers=headers, timeout=30)
    else:
        resp = httpx.get(f"{API_BASE}/{method}", params=params or {}, headers=headers, timeout=30)

    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After", "unknown")
        raise httpx.HTTPStatusError(
            f"rate limited on {method} (retry after {retry_after}s)",
            request=resp.request,
            response=resp,
        )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        error = data.get("error", "unknown error")
        if error in ("token_revoked", "token_expired", "invalid_auth", "not_authed"):
            _cached_token = None
            raise AuthError(f"Slack auth failed: {error} — run 'ak auth login slack'")
        raise ValueError(f"Slack API error: {error}")
    return data


def api_get(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a Slack Web API method via GET."""
    return _call(method, params=params)


def api_post(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a Slack Web API method via POST."""
    return _call(method, post=True, params=params)


def paginated_get(
    method: str, key: str, params: dict[str, Any] | None = None, *, limit: int = 100
) -> list[dict[str, Any]]:
    """Call a paginated Slack API method, collecting all results up to limit."""
    max_pages = 10
    params = dict(params or {})
    params["limit"] = 200
    results: list[dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        data = api_get(method, params)
        items = data.get(key, [])
        if not items:
            break
        results.extend(items)
        cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not cursor or len(results) >= limit:
            break
        params["cursor"] = cursor
        time.sleep(3)
    else:
        print(
            f"Warning: {method} hit max page limit ({max_pages}), results may be incomplete",
            file=sys.stderr,
        )

    return results[:limit]
