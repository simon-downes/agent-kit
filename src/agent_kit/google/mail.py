"""Gmail API client."""

import re
import subprocess
from base64 import urlsafe_b64decode
from pathlib import Path
from typing import Any

import httpx

from agent_kit.google.auth import get_token

API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    token = get_token()
    resp = httpx.get(
        f"{API_BASE}{path}",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code == 401:
        from agent_kit.google.auth import _refresh

        token = _refresh()
        resp = httpx.get(
            f"{API_BASE}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    if resp.status_code in (401, 403):
        resp.raise_for_status()
    if resp.status_code == 429:
        raise httpx.HTTPStatusError(
            "Google API rate limit exceeded, try again later",
            request=resp.request,
            response=resp,
        )
    if resp.status_code >= 400:
        _raise_error(resp)
    return resp.json()


def _raise_error(resp: httpx.Response) -> None:
    try:
        body = resp.json()
        msg = body.get("error", {}).get("message", "")
    except Exception:
        msg = ""
    if msg:
        raise ValueError(msg)
    resp.raise_for_status()


# --- List/search ---


def _format_message_summary(msg: dict[str, Any]) -> dict[str, Any]:
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    return {
        "id": msg["id"],
        "date": headers.get("date", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "snippet": msg.get("snippet", ""),
    }


def search_messages(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    data = _get("/messages", params={"q": query, "maxResults": limit})
    messages = data.get("messages", [])
    return [_format_message_summary(_get(f"/messages/{m['id']}")) for m in messages]


def list_recent(hours: int = 24, *, limit: int = 20) -> list[dict[str, Any]]:
    query = f"newer_than:{hours}h"
    return search_messages(query, limit=limit)


def list_unread(*, limit: int = 20) -> list[dict[str, Any]]:
    return search_messages("is:unread", limit=limit)


# --- Read single message ---


def get_message(message_id: str) -> dict[str, Any]:
    """Get full message with parsed body and attachment info."""
    msg = _get(f"/messages/{message_id}", params={"format": "full"})
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

    body = _extract_body(msg.get("payload", {}))
    attachments = _list_attachments(msg.get("payload", {}))

    return {
        "id": msg["id"],
        "date": headers.get("date", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "subject": headers.get("subject", ""),
        "body": body,
        "attachments": attachments,
    }


def download_attachment(message_id: str, attachment_id: str) -> bytes:
    """Download an attachment and return raw bytes."""
    data = _get(f"/messages/{message_id}/attachments/{attachment_id}")
    return urlsafe_b64decode(data["data"])


def write_message_to_file(message_id: str, output_dir: Path) -> tuple[Path, list[Path]]:
    """Download a message as markdown with attachments. Returns (md_path, attachment_paths)."""
    msg = get_message(message_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build filename from date and subject
    date_part = msg["date"][:10] if msg["date"] else "unknown"
    subject_slug = _slugify(msg["subject"] or "no-subject")
    basename = f"{date_part}-{subject_slug}"

    # Write markdown with frontmatter
    md_content = _format_as_markdown(msg)
    md_path = output_dir / f"{basename}.md"
    md_path.write_text(md_content)

    # Download attachments
    attachment_paths: list[Path] = []
    if msg["attachments"]:
        att_dir = output_dir / f"{basename}_attachments"
        att_dir.mkdir(exist_ok=True)
        for att in msg["attachments"]:
            data = download_attachment(message_id, att["id"])
            att_path = att_dir / att["filename"]
            att_path.write_bytes(data)
            attachment_paths.append(att_path)

    return md_path, attachment_paths


# --- Body extraction ---


def _extract_body(payload: dict[str, Any]) -> str:
    """Extract message body, preferring plain text, falling back to HTML → markdown."""
    plain = _find_part(payload, "text/plain")
    if plain:
        return urlsafe_b64decode(plain).decode("utf-8", errors="replace")

    html = _find_part(payload, "text/html")
    if html:
        html_str = urlsafe_b64decode(html).decode("utf-8", errors="replace")
        return html_to_markdown(html_str)

    return ""


def _find_part(payload: dict[str, Any], mime_type: str) -> str | None:
    """Recursively find a MIME part by type, return base64 data."""
    if payload.get("mimeType") == mime_type:
        body = payload.get("body", {})
        if body.get("data"):
            return body["data"]

    for part in payload.get("parts", []):
        result = _find_part(part, mime_type)
        if result:
            return result
    return None


def _list_attachments(payload: dict[str, Any]) -> list[dict[str, str]]:
    """List real attachments (not inline images)."""
    attachments: list[dict[str, str]] = []
    for part in payload.get("parts", []):
        filename = part.get("filename")
        if filename and part.get("body", {}).get("attachmentId"):
            attachments.append(
                {
                    "id": part["body"]["attachmentId"],
                    "filename": filename,
                    "mimeType": part.get("mimeType", ""),
                }
            )
        # Recurse into nested multipart
        attachments.extend(_list_attachments(part))
    return attachments


# --- HTML → Markdown ---


def html_to_markdown(html: str) -> str:
    """Convert HTML to markdown. Uses pandoc if available, falls back to basic stripping."""
    # Strip inline images (signature logos, tracking pixels)
    html = re.sub(r"<img[^>]*>", "", html, flags=re.IGNORECASE)

    try:
        result = subprocess.run(
            ["pandoc", "-f", "html", "-t", "markdown", "--wrap=none"],
            input=html,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: basic HTML tag stripping
    return _strip_html(html)


def _strip_html(html: str) -> str:
    """Basic HTML → plain text fallback."""
    # Remove style and script blocks
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- Helpers ---


def _format_as_markdown(msg: dict[str, Any]) -> str:
    """Format a message as markdown with YAML frontmatter."""
    lines = ["---"]
    lines.append(f"from: {_yaml_escape(msg['from'])}")
    lines.append(f"to: {_yaml_escape(msg['to'])}")
    if msg.get("cc"):
        lines.append(f"cc: {_yaml_escape(msg['cc'])}")
    lines.append(f"date: {_yaml_escape(msg['date'])}")
    lines.append(f"subject: {_yaml_escape(msg['subject'])}")
    lines.append("---")
    lines.append("")
    lines.append(msg["body"])
    return "\n".join(lines)


def _yaml_escape(value: str) -> str:
    """Escape a value for safe YAML output."""
    if not value:
        return '""'
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")
