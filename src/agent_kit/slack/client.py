"""Slack webhook client."""

import sys

import httpx


def send_message(
    webhook_url: str,
    text: str,
    *,
    header: str | None = None,
    fields: list[tuple[str, str]] | None = None,
) -> None:
    """Send a message to Slack via incoming webhook.

    Builds a Block Kit payload from the provided components.
    Raises SystemExit on failure.
    """
    blocks: list[dict] = []

    if header:
        blocks.append({"type": "header", "text": {"type": "plain_text", "text": header}})

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

    if fields:
        blocks.append(
            {
                "type": "section",
                "fields": [{"type": "mrkdwn", "text": f"*{k}*\n{v}"} for k, v in fields],
            }
        )

    payload = {"text": text, "blocks": blocks}
    _post(webhook_url, payload)


def send_raw(webhook_url: str, payload: dict) -> None:
    """Send a raw JSON payload to Slack via incoming webhook."""
    _post(webhook_url, payload)


def _post(webhook_url: str, payload: dict) -> None:
    """POST a payload to a Slack webhook URL."""
    resp = httpx.post(webhook_url, json=payload)
    if resp.status_code != 200:
        print(f"Error: Slack returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)
