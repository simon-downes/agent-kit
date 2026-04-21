"""Channel and user resolution with file-based caching."""

import json
import time
from pathlib import Path
from typing import Any

from agent_kit.slack.client import SlackClient

CACHE_TTL = 3600  # 1 hour

_cache_dir: Path | None = None


# --- Cache helpers ---


def _get_cache_dir() -> Path:
    """Get cache directory."""
    global _cache_dir
    if _cache_dir is None:
        primary = Path("~/.agent-kit/cache").expanduser()
        try:
            primary.mkdir(parents=True, exist_ok=True)
            _cache_dir = primary
        except OSError:
            _cache_dir = Path("/tmp/agent-kit-cache")
            _cache_dir.mkdir(parents=True, exist_ok=True)
    return _cache_dir


def _read_cache(name: str) -> Any | None:
    """Read a cache file if it exists and is within TTL."""
    path = _get_cache_dir() / f"slack-{name}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data.get("ts", 0) < CACHE_TTL:
            return data["items"]
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _write_cache(name: str, items: Any) -> None:
    """Write items to a cache file."""
    path = _get_cache_dir() / f"slack-{name}.json"
    path.write_text(json.dumps({"ts": time.time(), "items": items}))


# --- Users ---

_user_cache: dict[str, dict[str, str]] | None = None


def get_users(client: SlackClient, *, no_cache: bool = False) -> dict[str, dict[str, str]]:
    """Get all users. Cached to file with 1hr TTL."""
    global _user_cache
    if _user_cache is not None and not no_cache:
        return _user_cache

    if not no_cache:
        cached = _read_cache("users")
        if cached is not None:
            _user_cache = cached
            return _user_cache

    members = client.get_users()
    result: dict[str, dict[str, str]] = {}
    for m in members:
        if m.get("deleted") or m.get("is_bot"):
            continue
        profile = m.get("profile", {})
        result[m["id"]] = {
            "id": m["id"],
            "name": m.get("name", ""),
            "real_name": m.get("real_name", profile.get("real_name", "")),
            "display_name": profile.get("display_name", ""),
            "email": profile.get("email", ""),
        }

    _user_cache = result
    _write_cache("users", result)
    return _user_cache


def resolve_user_name(client: SlackClient, user_id: str) -> str:
    """Resolve a user ID to a display name."""
    users = get_users(client)
    user = users.get(user_id)
    if not user:
        return user_id
    return user.get("display_name") or user.get("real_name") or user.get("name") or user_id


def search_users(client: SlackClient, query: str) -> list[dict[str, str]]:
    """Search users by name (case-insensitive partial match)."""
    users = get_users(client)
    query_lower = query.lower()
    return [
        u
        for u in users.values()
        if query_lower in u.get("name", "").lower()
        or query_lower in u.get("real_name", "").lower()
        or query_lower in u.get("display_name", "").lower()
    ]


# --- Channels ---

_channel_cache: list[dict[str, Any]] | None = None


def get_channels(
    client: SlackClient, *, include_archived: bool = False, no_cache: bool = False
) -> list[dict[str, Any]]:
    """Get public and private channels. Cached to file with 1hr TTL."""
    global _channel_cache
    if _channel_cache is not None and not no_cache:
        return _channel_cache

    if not no_cache:
        cached = _read_cache("channels")
        if cached is not None:
            _channel_cache = cached
            return _channel_cache

    channels = client.get_channels(include_archived=include_archived)
    _channel_cache = channels
    _write_cache("channels", channels)
    return _channel_cache


# --- DMs ---

_dm_cache: list[dict[str, Any]] | None = None


def get_dms(
    client: SlackClient, *, include_group: bool = False, no_cache: bool = False
) -> list[dict[str, Any]]:
    """Get DM conversations. Cached to file with 1hr TTL."""
    global _dm_cache
    if _dm_cache is not None and not no_cache:
        return _filter_dms(_dm_cache, include_group)

    if not no_cache:
        cached = _read_cache("dms")
        if cached is not None:
            _dm_cache = cached
            return _filter_dms(cached, include_group)

    dms = client.get_dms()
    _dm_cache = dms
    _write_cache("dms", dms)
    return _filter_dms(dms, include_group)


def _filter_dms(dms: list[dict[str, Any]], include_group: bool) -> list[dict[str, Any]]:
    if include_group:
        return dms
    return [d for d in dms if not d.get("is_mpim")]


# --- Resolution ---


def resolve_channel(client: SlackClient, name_or_id: str) -> tuple[str, str | None]:
    """Resolve a channel name or ID to (channel_id, channel_type).

    Accepts #name, @user (for DMs), or raw channel ID.
    """
    if name_or_id.startswith("#"):
        name = name_or_id[1:]
        for c in get_channels(client):
            if c.get("name") == name:
                return c["id"], _channel_type(c)
        raise ValueError(f"channel #{name} not found")

    if name_or_id.startswith("@"):
        username = name_or_id[1:]
        users = get_users(client)
        for uid, u in users.items():
            if username.lower() in (
                u.get("name", "").lower(),
                u.get("display_name", "").lower(),
            ):
                resp = client.open_conversation(uid)
                ch = resp.get("channel", {})
                return ch["id"], "im"
        raise ValueError(f"user @{username} not found")

    # Raw ID — check channels then DMs
    for c in get_channels(client):
        if c["id"] == name_or_id:
            return c["id"], _channel_type(c)
    for d in get_dms(client, include_group=True):
        if d["id"] == name_or_id:
            return d["id"], _channel_type(d)
    return name_or_id, None


def _channel_type(channel: dict[str, Any]) -> str:
    if channel.get("is_im"):
        return "im"
    if channel.get("is_mpim"):
        return "mpim"
    if channel.get("is_private"):
        return "private"
    return "public"
