"""Channel and user resolution for Slack."""

from typing import Any

from agent_kit.slack.api import paginated_get

_user_cache: dict[str, dict[str, str]] | None = None
_channel_cache: list[dict[str, Any]] | None = None


def get_users() -> dict[str, dict[str, str]]:
    """Get all users, cached for the session. Returns {user_id: {name, real_name, ...}}."""
    global _user_cache
    if _user_cache is not None:
        return _user_cache

    members = paginated_get("users.list", "members", limit=1000)
    _user_cache = {}
    for m in members:
        if m.get("deleted") or m.get("is_bot"):
            continue
        profile = m.get("profile", {})
        _user_cache[m["id"]] = {
            "id": m["id"],
            "name": m.get("name", ""),
            "real_name": m.get("real_name", profile.get("real_name", "")),
            "display_name": profile.get("display_name", ""),
            "email": profile.get("email", ""),
        }
    return _user_cache


def resolve_user_name(user_id: str) -> str:
    """Resolve a user ID to a display name."""
    users = get_users()
    user = users.get(user_id)
    if not user:
        return user_id
    return user.get("display_name") or user.get("real_name") or user.get("name") or user_id


def search_users(query: str) -> list[dict[str, str]]:
    """Search users by name (case-insensitive partial match)."""
    users = get_users()
    query_lower = query.lower()
    return [
        u
        for u in users.values()
        if query_lower in u.get("name", "").lower()
        or query_lower in u.get("real_name", "").lower()
        or query_lower in u.get("display_name", "").lower()
    ]


def get_channels(
    *, include_dms: bool = False, include_group_dms: bool = False
) -> list[dict[str, Any]]:
    """Get channels, cached for the session."""
    global _channel_cache
    if _channel_cache is not None:
        return _filter_channels(_channel_cache, include_dms, include_group_dms)

    types = "public_channel,private_channel"
    if include_dms:
        types += ",im"
    if include_group_dms:
        types += ",mpim"

    channels = paginated_get("conversations.list", "channels", params={"types": types}, limit=1000)
    _channel_cache = channels
    return _filter_channels(channels, include_dms, include_group_dms)


def _filter_channels(
    channels: list[dict[str, Any]], include_dms: bool, include_group_dms: bool
) -> list[dict[str, Any]]:
    result = []
    for c in channels:
        if c.get("is_im") and not include_dms:
            continue
        if c.get("is_mpim") and not include_group_dms:
            continue
        result.append(c)
    return result


def resolve_channel(name_or_id: str) -> tuple[str, str | None]:
    """Resolve a channel name or ID to (channel_id, channel_type).

    Accepts #name, @user (for DMs), or raw channel ID.
    """
    if name_or_id.startswith("#"):
        name = name_or_id[1:]
        channels = get_channels(include_dms=True, include_group_dms=True)
        for c in channels:
            if c.get("name") == name:
                return c["id"], _channel_type(c)
        raise ValueError(f"channel #{name} not found")

    if name_or_id.startswith("@"):
        username = name_or_id[1:]
        users = get_users()
        for uid, u in users.items():
            if username.lower() in (
                u.get("name", "").lower(),
                u.get("display_name", "").lower(),
            ):
                # Open a DM channel
                from agent_kit.slack.api import api_get

                resp = api_get("conversations.open", {"users": uid})
                ch = resp.get("channel", {})
                return ch["id"], "im"
        raise ValueError(f"user @{username} not found")

    # Raw ID — look up type from cache if available
    channels = get_channels(include_dms=True, include_group_dms=True)
    for c in channels:
        if c["id"] == name_or_id:
            return c["id"], _channel_type(c)
    return name_or_id, None


def _channel_type(channel: dict[str, Any]) -> str:
    if channel.get("is_im"):
        return "im"
    if channel.get("is_mpim"):
        return "mpim"
    if channel.get("is_private"):
        return "private"
    return "public"
