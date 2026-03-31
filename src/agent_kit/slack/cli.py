"""Slack CLI subcommands."""

import json
import os
import sys

import click

from agent_kit.slack.client import send_message, send_raw


def _get_webhook_url() -> str:
    """Get webhook URL from environment or exit."""
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        print("Error: SLACK_WEBHOOK_URL environment variable is not set", file=sys.stderr)
        sys.exit(2)
    return url


@click.group()
def slack() -> None:
    """Slack — send messages via incoming webhooks."""


@slack.command()
@click.argument("text", required=False)
@click.option("--header", help="Header block text")
@click.option("--field", "fields", multiple=True, help="Key=Value field (repeatable)")
@click.option("--json", "use_json", is_flag=True, help="Read raw JSON payload from stdin")
def send(text: str | None, header: str | None, fields: tuple[str, ...], use_json: bool) -> None:
    """Send a message to Slack.

    Text can be provided as an argument or piped via stdin.
    Supports mrkdwn formatting.
    """
    url = _get_webhook_url()

    if use_json:
        raw = sys.stdin.read().strip()
        if not raw:
            print("Error: no JSON payload on stdin", file=sys.stderr)
            sys.exit(1)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON: {e}", file=sys.stderr)
            sys.exit(1)
        send_raw(url, payload)
        return

    # Read text from stdin if not provided as argument
    if not text:
        if sys.stdin.isatty():
            print("Error: provide message text as argument or via stdin", file=sys.stderr)
            sys.exit(1)
        text = sys.stdin.read().strip()

    if not text:
        print("Error: empty message", file=sys.stderr)
        sys.exit(1)

    parsed_fields = None
    if fields:
        parsed_fields = []
        for f in fields:
            if "=" not in f:
                print(f"Error: invalid field format '{f}', expected Key=Value", file=sys.stderr)
                sys.exit(1)
            k, v = f.split("=", 1)
            parsed_fields.append((k, v))

    send_message(url, text, header=header, fields=parsed_fields)
