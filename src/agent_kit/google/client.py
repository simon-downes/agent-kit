"""Google Workspace API client with auto-refreshing OAuth tokens."""

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from agent_kit.auth import set_fields
from agent_kit.config import load_config
from agent_kit.errors import AuthError


class GoogleClient:
    """Client for Google Workspace APIs (Gmail, Calendar, Drive)."""

    def __init__(self, credentials: dict[str, str]):
        token = credentials.get("access_token")
        if not token:
            raise AuthError("no Google credentials — run 'ak auth login google'")
        self._token = token
        self._expires_at = credentials.get("expires_at")
        self._refresh_token = credentials.get("refresh_token")
        self._client_id = credentials.get("client_id")
        self._client_secret = credentials.get("client_secret")
        if self._expires_at and self._is_expired(self._expires_at):
            self._do_refresh()

    # --- Public interface: Mail ---

    def mail_search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        from agent_kit.google.mail import search_messages

        return search_messages(self, query, limit=limit)

    def mail_recent(self, hours: int = 24, *, limit: int = 20) -> list[dict[str, Any]]:
        from agent_kit.google.mail import list_recent

        return list_recent(self, hours, limit=limit)

    def mail_unread(self, *, limit: int = 20) -> list[dict[str, Any]]:
        from agent_kit.google.mail import list_unread

        return list_unread(self, limit=limit)

    def mail_read(self, message_id: str) -> dict[str, Any]:
        from agent_kit.google.mail import get_message

        return get_message(self, message_id)

    def mail_download(self, message_id: str, output_dir: Path) -> tuple[Path, list[Path]]:
        from agent_kit.google.mail import write_message_to_file

        return write_message_to_file(self, message_id, output_dir)

    # --- Public interface: Calendar ---

    def calendar_today(self) -> list[dict[str, Any]]:
        from agent_kit.google.calendar import get_today

        return get_today(self)

    def calendar_upcoming(self, days: int = 7) -> list[dict[str, Any]]:
        from agent_kit.google.calendar import get_upcoming

        return get_upcoming(self, days)

    def calendar_event(self, event_id: str) -> dict[str, Any]:
        from agent_kit.google.calendar import get_event

        return get_event(self, event_id)

    # --- Public interface: Drive ---

    def drive_search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        from agent_kit.google.drive import search_files

        return search_files(self, query, limit=limit)

    def drive_recent(self, days: int = 7, *, limit: int = 20) -> list[dict[str, Any]]:
        from agent_kit.google.drive import get_recent

        return get_recent(self, days, limit=limit)

    def drive_list(self, *, folder_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        from agent_kit.google.drive import list_files

        return list_files(self, folder_id=folder_id, limit=limit)

    def drive_fetch(
        self, file_id: str, output_dir: Path, *, format_override: str | None = None
    ) -> Path:
        from agent_kit.google.drive import fetch_file

        return fetch_file(self, file_id, output_dir, format_override=format_override)

    def drive_fetch_stdout(self, file_id: str) -> str:
        from agent_kit.google.drive import fetch_to_stdout

        return fetch_to_stdout(self, file_id)

    # --- Private implementation ---

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        follow_redirects: bool = False,
    ) -> httpx.Response:
        """Make an authenticated HTTP request with 401->refresh->retry."""
        hdrs = {**(headers or {}), "Authorization": f"Bearer {self._token}"}
        resp = httpx.request(
            method,
            url,
            params=params,
            headers=hdrs,
            timeout=timeout,
            follow_redirects=follow_redirects,
        )
        if resp.status_code == 401:
            self._do_refresh()
            hdrs["Authorization"] = f"Bearer {self._token}"
            resp = httpx.request(
                method,
                url,
                params=params,
                headers=hdrs,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )
        return resp

    @staticmethod
    def _is_expired(expires_at: str) -> bool:
        """Check if token is expired or within 60s of expiry."""
        try:
            expiry = datetime.fromisoformat(expires_at)
            return (expiry - datetime.now(UTC)).total_seconds() < 60
        except (ValueError, TypeError):
            return True

    def _do_refresh(self) -> None:
        """Refresh the access token using the refresh token."""
        from agent_kit.auth.oauth import refresh_token

        config = load_config()
        auth_config = config.get("auth", {}).get("google", {})
        token_endpoint = auth_config.get("token_endpoint")

        if not all([token_endpoint, self._client_id, self._refresh_token]):
            raise AuthError(
                "missing Google OAuth config or refresh token — run 'ak auth login google'"
            )

        print("Refreshing Google token...", file=sys.stderr)
        tokens = refresh_token(
            token_endpoint,
            self._client_id,
            self._refresh_token,
            client_secret=self._client_secret,
        )

        self._token = tokens["access_token"]
        if "refresh_token" in tokens:
            self._refresh_token = tokens["refresh_token"]

        token_data: dict[str, str] = {"access_token": tokens["access_token"]}
        if "refresh_token" in tokens:
            token_data["refresh_token"] = tokens["refresh_token"]
        if "expires_in" in tokens:
            expires_at = datetime.now(UTC).timestamp() + tokens["expires_in"]
            iso = datetime.fromtimestamp(expires_at, UTC).isoformat()
            token_data["expires_at"] = iso
            self._expires_at = iso

        try:
            set_fields("google", token_data)
        except OSError:
            print(
                "Warning: could not persist refreshed token (read-only filesystem)",
                file=sys.stderr,
            )
