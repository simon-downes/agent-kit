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


@click.group()
def slack() -> None:
    """Slack — channels, messages, search, and webhooks."""


# --- Read commands ---


@slack.command()
@click.option("--limit", default=100, help="Maximum results")
@handle_errors
def channels(limit: int) -> None:
    """List channels you're in."""
    from agent_kit.config import load_config
    from agent_kit.slack.api import require_read
    from agent_kit.slack.resolve import get_channels

    require_read()
    config = load_config()
    scope = config.get("slack", {}).get("read", {}).get("scope", {})

    chs = get_channels(
        include_dms=scope.get("include_dms", False),
        include_group_dms=scope.get("include_group_dms", False),
    )

    allowed = scope.get("channels", [])
    result = []
    for c in chs[:limit]:
        if allowed and c.get("name") not in allowed and f"#{c.get('name')}" not in allowed:
            if c["id"] not in allowed:
                continue
        ch_type = "public"
        if c.get("is_im"):
            ch_type = "dm"
        elif c.get("is_mpim"):
            ch_type = "group_dm"
        elif c.get("is_private"):
            ch_type = "private"
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
@click.argument("channel")
@click.option("--limit", default=50, help="Maximum messages")
@click.option("--since", default=24, help="Hours to look back (default: 24)")
@handle_errors
def history(channel: str, limit: int, since: int) -> None:
    """Read recent messages from a channel."""
    from agent_kit.slack.api import api_get, require_read
    from agent_kit.slack.resolve import check_channel_scope, resolve_channel, resolve_user_name

    require_read()
    channel_id, channel_type = resolve_channel(channel)
    check_channel_scope(channel_id, channel_type)

    oldest = str(time.time() - (since * 3600))
    data = api_get(
        "conversations.history",
        {"channel": channel_id, "limit": limit, "oldest": oldest},
    )

    messages = []
    for m in reversed(data.get("messages", [])):
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
@handle_errors
def thread(channel: str, thread_ts: str) -> None:
    """Read thread replies."""
    from agent_kit.slack.api import api_get, require_read
    from agent_kit.slack.resolve import check_channel_scope, resolve_channel, resolve_user_name

    require_read()
    channel_id, channel_type = resolve_channel(channel)
    check_channel_scope(channel_id, channel_type)

    data = api_get(
        "conversations.replies",
        {"channel": channel_id, "ts": thread_ts},
    )

    messages = [
        {
            "ts": m.get("ts"),
            "user": resolve_user_name(m.get("user", "")),
            "text": m.get("text", ""),
        }
        for m in data.get("messages", [])
    ]
    output(messages)


@slack.command()
@click.argument("query")
@click.option("--limit", default=20, help="Maximum results")
@handle_errors
def search(query: str, limit: int) -> None:
    """Search messages (Slack query syntax, sorted by date)."""
    from agent_kit.slack.api import api_get, require_read
    from agent_kit.slack.resolve import resolve_user_name

    require_read()
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
@handle_errors
def users(query: str | None, limit: int) -> None:
    """List or search workspace users."""
    from agent_kit.slack.api import require_read
    from agent_kit.slack.resolve import get_users, search_users

    require_read()
    if query:
        result = search_users(query)
    else:
        result = list(get_users().values())
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

    # Read text from stdin if not provided as argument
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
