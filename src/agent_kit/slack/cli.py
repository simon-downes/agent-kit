"""Slack CLI subcommands."""

import json
import os
import sys
import time

import click

from agent_kit.errors import AuthError, handle_errors, output
from agent_kit.slack.client import send_message, send_raw


def _get_webhook_url() -> str:
    """Get webhook URL from credential store or environment."""
    from agent_kit.auth import get_field

    url = get_field("slack", "webhook_url") or os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        raise AuthError("no Slack credentials — run 'ak auth set slack webhook_url'")
    return url


def _load_config() -> dict:
    """Load config once per command."""
    from agent_kit.config import load_config

    return load_config()


@click.group()
def slack() -> None:
    """Slack — channels, messages, search, and webhooks."""


# --- Read commands ---


@slack.command()
@click.option("--limit", default=100, help="Maximum results")
@click.option("--archived", is_flag=True, help="Include archived channels")
@click.option("--no-cache", is_flag=True, help="Bypass cache and fetch from API")
@handle_errors
def channels(limit: int, archived: bool, no_cache: bool) -> None:
    """List public and private channels."""
    from agent_kit.slack.api import require_read
    from agent_kit.slack.resolve import get_channels

    config = _load_config()
    require_read(config)

    chs = get_channels(include_archived=archived, no_cache=no_cache)

    result = []
    for c in chs[:limit]:
        ch_type = "private" if c.get("is_private") else "public"
        result.append(
            {
                "id": c["id"],
                "name": c.get("name", ""),
                "type": ch_type,
                "member_count": c.get("num_members", 0),
            }
        )
    output(result)


@slack.command()
@click.option("--limit", default=100, help="Maximum results")
@click.option("--group", is_flag=True, help="Include group DMs")
@click.option("--no-cache", is_flag=True, help="Bypass cache and fetch from API")
@handle_errors
def dms(limit: int, group: bool, no_cache: bool) -> None:
    """List DM conversations."""
    from agent_kit.slack.api import require_read
    from agent_kit.slack.resolve import get_dms, resolve_user_name

    config = _load_config()
    require_read(config)

    conversations = get_dms(include_group=group, no_cache=no_cache)

    result = []
    for d in conversations[:limit]:
        if d.get("is_mpim"):
            name = d.get("name", d["id"])
            dm_type = "group_dm"
        else:
            name = resolve_user_name(d.get("user", ""))
            dm_type = "dm"
        result.append({"id": d["id"], "name": name, "type": dm_type})
    output(result)


@slack.command()
@click.argument("channel")
@click.option("--limit", default=50, help="Maximum messages")
@click.option("--since", default=24, help="Hours to look back (default: 24)")
@handle_errors
def history(channel: str, limit: int, since: int) -> None:
    """Read recent messages from a channel or DM."""
    from agent_kit.slack.api import check_channel_scope, paginated_get, require_read
    from agent_kit.slack.resolve import resolve_channel, resolve_user_name

    config = _load_config()
    require_read(config)
    channel_id, channel_type = resolve_channel(channel)
    check_channel_scope(config, channel_id, channel_type)

    oldest = str(time.time() - (since * 3600))
    results = paginated_get(
        "conversations.history",
        "messages",
        {"channel": channel_id, "oldest": oldest},
        limit=limit,
    )

    messages = []
    for m in reversed(results):
        messages.append(
            {
                "ts": m.get("ts"),
                "user": resolve_user_name(m.get("user", "")),
                "text": m.get("text", ""),
                "thread_ts": m.get("thread_ts") if m.get("reply_count") else None,
                "reply_count": m.get("reply_count", 0),
            }
        )
    output(messages)


@slack.command()
@click.argument("channel")
@click.argument("thread_ts")
@click.option("--limit", default=100, help="Maximum replies")
@handle_errors
def thread(channel: str, thread_ts: str, limit: int) -> None:
    """Read thread replies."""
    from agent_kit.slack.api import check_channel_scope, paginated_get, require_read
    from agent_kit.slack.resolve import resolve_channel, resolve_user_name

    config = _load_config()
    require_read(config)
    channel_id, channel_type = resolve_channel(channel)
    check_channel_scope(config, channel_id, channel_type)

    results = paginated_get(
        "conversations.replies",
        "messages",
        {"channel": channel_id, "ts": thread_ts},
        limit=limit,
    )

    messages = [
        {
            "ts": m.get("ts"),
            "user": resolve_user_name(m.get("user", "")),
            "text": m.get("text", ""),
        }
        for m in results
    ]
    output(messages)


@slack.command()
@click.argument("query")
@click.option("--limit", default=20, help="Maximum results (max 100)")
@handle_errors
def search(query: str, limit: int) -> None:
    """Search messages (Slack query syntax, sorted by date)."""
    from agent_kit.slack.api import api_get, require_read
    from agent_kit.slack.resolve import resolve_user_name

    config = _load_config()
    require_read(config)
    limit = min(limit, 100)
    data = api_get(
        "search.messages",
        {"query": query, "count": limit, "sort": "timestamp", "sort_dir": "desc"},
    )

    matches = data.get("messages", {}).get("matches", [])
    result = [
        {
            "channel": m.get("channel", {}).get("name", ""),
            "ts": m.get("ts"),
            "user": resolve_user_name(m.get("user", m.get("username", ""))),
            "text": m.get("text", ""),
            "permalink": m.get("permalink", ""),
        }
        for m in matches
    ]
    output(result)


@slack.command()
@click.argument("query", required=False)
@click.option("--limit", default=50, help="Maximum results")
@click.option("--no-cache", is_flag=True, help="Bypass cache and fetch from API")
@handle_errors
def users(query: str | None, limit: int, no_cache: bool) -> None:
    """List or search workspace users."""
    from agent_kit.slack.api import require_read
    from agent_kit.slack.resolve import get_users, search_users

    config = _load_config()
    require_read(config)
    if query:
        result = search_users(query)
    else:
        result = list(get_users(no_cache=no_cache).values())
    output(result[:limit])


# --- Write commands (existing webhook) ---


@slack.command()
@click.argument("text", required=False)
@click.option("--header", help="Header block text")
@click.option("--field", "fields", multiple=True, help="Key=Value field (repeatable)")
@click.option("--json", "use_json", is_flag=True, help="Read raw JSON payload from stdin")
@handle_errors
def send(text: str | None, header: str | None, fields: tuple[str, ...], use_json: bool) -> None:
    """Send a message to Slack.

    Text can be provided as an argument or piped via stdin.
    Supports mrkdwn formatting.
    """
    url = _get_webhook_url()

    if use_json:
        raw = sys.stdin.read().strip()
        if not raw:
            raise ValueError("no JSON payload on stdin")
        payload = json.loads(raw)
        send_raw(url, payload)
        print("OK")
        return

    if not text:
        if sys.stdin.isatty():
            raise ValueError("provide message text as argument or via stdin")
        text = sys.stdin.read().strip()

    if not text:
        raise ValueError("empty message")

    parsed_fields = None
    if fields:
        parsed_fields = []
        for f in fields:
            if "=" not in f:
                raise ValueError(f"invalid field format '{f}', expected Key=Value")
            k, v = f.split("=", 1)
            parsed_fields.append((k, v))

    send_message(url, text, header=header, fields=parsed_fields)
    print("OK")
