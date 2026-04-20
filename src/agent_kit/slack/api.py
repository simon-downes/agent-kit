"""Slack Web API client for read operations."""

from typing import Any

import httpx

from agent_kit.config import load_config
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


def require_read() -> None:
    """Check that Slack read is enabled."""
    config = load_config()
    if not config.get("slack", {}).get("read", {}).get("enabled", True):
        raise ConfigError("Slack read operations are disabled in config")


def check_channel_scope(channel_id: str, channel_type: str | None = None) -> None:
    """Check if a channel is within the configured scope."""
    config = load_config()
    scope = config.get("slack", {}).get("read", {}).get("scope", {})

    if channel_type in ("im",) and not scope.get("include_dms", False):
        raise ConfigError("DM access is disabled in config (set slack.read.scope.include_dms)")
    if channel_type in ("mpim",) and not scope.get("include_group_dms", False):
        raise ConfigError(
            "Group DM access is disabled in config (set slack.read.scope.include_group_dms)"
        )

    allowed = scope.get("channels", [])
    if allowed and channel_id not in allowed and f"#{channel_id}" not in allowed:
        raise ConfigError(f"channel {channel_id} is not in the configured scope")


def api_get(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a Slack Web API method."""
    token = get_user_token()
    resp = httpx.get(
        f"{API_BASE}/{method}",
        params=params or {},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code == 429:
        raise httpx.HTTPStatusError(
            "Slack API rate limit exceeded, try again later",
            request=resp.request,
            response=resp,
        )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        error = data.get("error", "unknown error")
        if error in ("token_revoked", "token_expired", "invalid_auth", "not_authed"):
            raise AuthError(f"Slack auth failed: {error} — run 'ak auth login slack'")
        raise ValueError(f"Slack API error: {error}")
    return data


def paginated_get(
    method: str, key: str, params: dict[str, Any] | None = None, *, limit: int = 100
) -> list[dict[str, Any]]:
    """Call a paginated Slack API method, collecting all results up to limit."""
    params = dict(params or {})
    params["limit"] = min(limit, 200)
    results: list[dict[str, Any]] = []

    while len(results) < limit:
        data = api_get(method, params)
        results.extend(data.get(key, []))
        cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        params["cursor"] = cursor

    return results[:limit]
