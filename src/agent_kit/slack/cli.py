"""Slack CLI subcommands."""

import json
import os
import sys

import click

from agent_kit.errors import AuthError, handle_errors
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
    """Slack — send messages via incoming webhooks."""


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
