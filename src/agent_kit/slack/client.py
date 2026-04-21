"""Slack API client — Web API reads and webhook writes."""

import sys
import time
from typing import Any

import httpx

from agent_kit.errors import AuthError

API_BASE = "https://slack.com/api"


class SlackClient:
    """Client for Slack Web API and webhooks."""

    def __init__(self, token: str, *, webhook_url: str | None = None):
        self._token = token
        self._webhook_url = webhook_url

    # --- Public interface ---

    def get_channels(
        self, *, include_archived: bool = False, limit: int = 1000
    ) -> list[dict[str, Any]]:
        """Get public and private channels."""
        params: dict[str, Any] = {"types": "public_channel,private_channel"}
        if not include_archived:
            params["exclude_archived"] = "true"
        return self._paginated_get("conversations.list", "channels", params=params, limit=limit)

    def get_dms(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        """Get all DM conversations (1:1 and group)."""
        return self._paginated_get(
            "conversations.list", "channels", params={"types": "im,mpim"}, limit=limit
        )

    def get_users(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        """Get workspace members (raw API response)."""
        return self._paginated_get("users.list", "members", limit=limit)

    def get_history(
        self, channel_id: str, *, oldest: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get channel message history."""
        params: dict[str, Any] = {"channel": channel_id}
        if oldest:
            params["oldest"] = oldest
        return self._paginated_get("conversations.history", "messages", params=params, limit=limit)

    def get_thread(self, channel_id: str, thread_ts: str, *, limit: int = 100) -> list[dict]:
        """Get thread replies."""
        return self._paginated_get(
            "conversations.replies",
            "messages",
            params={"channel": channel_id, "ts": thread_ts},
            limit=limit,
        )

    def search_messages(self, query: str, *, limit: int = 20) -> dict[str, Any]:
        """Search messages. Returns raw API response (uses classic pagination)."""
        limit = min(limit, 100)
        return self._get(
            "search.messages",
            {"query": query, "count": limit, "sort": "timestamp", "sort_dir": "desc"},
        )

    def open_conversation(self, user_id: str) -> dict[str, Any]:
        """Open a DM conversation with a user."""
        return self._post("conversations.open", {"users": user_id})

    def send_webhook(
        self,
        text: str,
        *,
        header: str | None = None,
        fields: list[tuple[str, str]] | None = None,
    ) -> None:
        """Send a message via incoming webhook."""
        if not self._webhook_url:
            raise AuthError("no webhook URL configured")
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
        self._post_webhook({"text": text, "blocks": blocks})

    def send_webhook_raw(self, payload: dict) -> None:
        """Send a raw JSON payload via incoming webhook."""
        if not self._webhook_url:
            raise AuthError("no webhook URL configured")
        self._post_webhook(payload)

    # --- Private implementation ---

    def _get(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a Slack Web API method via GET."""
        return self._call(method, params=params)

    def _post(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a Slack Web API method via POST."""
        return self._call(method, post=True, params=params)

    def _call(self, method: str, *, post: bool = False, params: dict[str, Any] | None = None):
        """Execute a Slack Web API call."""
        headers = {"Authorization": f"Bearer {self._token}"}
        if post:
            resp = httpx.post(
                f"{API_BASE}/{method}", data=params or {}, headers=headers, timeout=30
            )
        else:
            resp = httpx.get(
                f"{API_BASE}/{method}", params=params or {}, headers=headers, timeout=30
            )

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
                raise AuthError(f"Slack auth failed: {error} — run 'ak auth login slack'")
            raise ValueError(f"Slack API error: {error}")
        return data

    def _paginated_get(
        self, method: str, key: str, params: dict[str, Any] | None = None, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Paginate a Slack API method, collecting results up to limit."""
        max_pages = 10
        params = dict(params or {})
        params["limit"] = 200
        results: list[dict[str, Any]] = []

        for page in range(1, max_pages + 1):
            data = self._get(method, params)
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

    def _post_webhook(self, payload: dict) -> None:
        """POST a payload to the webhook URL."""
        resp = httpx.post(self._webhook_url, json=payload)
        resp.raise_for_status()
