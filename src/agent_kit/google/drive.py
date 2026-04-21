"""Google Drive API operations."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_kit.google.client import GoogleClient

API_BASE = "https://www.googleapis.com/drive/v3"

GOOGLE_DOC_TYPES = {
    "application/vnd.google-apps.document": {"export": "text/html", "ext": ".md"},
    "application/vnd.google-apps.spreadsheet": {"export": "text/csv", "ext": ".csv"},
    "application/vnd.google-apps.presentation": {"export": "text/html", "ext": ".md"},
}

FORMAT_MIME = {
    "html": "text/html",
    "pdf": "application/pdf",
    "csv": "text/csv",
    "text": "text/plain",
}


def _get(client: GoogleClient, path: str, params: dict[str, Any] | None = None) -> Any:
    params = {**(params or {}), "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
    resp = client._request("GET", f"{API_BASE}{path}", params=params)
    if resp.status_code in (401, 403):
        resp.raise_for_status()
    if resp.status_code == 429:
        raise ValueError("Google API rate limit exceeded, try again later")
    if resp.status_code >= 400:
        _raise_error(resp)
    return resp.json()


def _download(client: GoogleClient, url: str) -> bytes:
    resp = client._request("GET", url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def _raise_error(resp) -> None:
    try:
        body = resp.json()
        msg = body.get("error", {}).get("message", "")
    except Exception:
        msg = ""
    if msg:
        raise ValueError(msg)
    resp.raise_for_status()


def _format_file(f: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f["id"],
        "name": f.get("name", ""),
        "mimeType": f.get("mimeType", ""),
        "modifiedTime": f.get("modifiedTime", ""),
        "owners": [o.get("emailAddress", "") for o in f.get("owners", [])],
    }


# --- Search / List ---


def search_files(client: GoogleClient, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    q = f"name contains '{_escape(query)}' or fullText contains '{_escape(query)}'"
    q += " and trashed = false"
    data = _get(
        client,
        "/files",
        params={
            "q": q,
            "pageSize": limit,
            "fields": "files(id,name,mimeType,modifiedTime,owners)",
            "orderBy": "modifiedTime desc",
        },
    )
    return [_format_file(f) for f in data.get("files", [])]


def list_files(
    client: GoogleClient, *, folder_id: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    q = "trashed = false"
    if folder_id:
        q += f" and '{_escape(folder_id)}' in parents"
    else:
        q += " and 'root' in parents"
    data = _get(
        client,
        "/files",
        params={
            "q": q,
            "pageSize": limit,
            "fields": "files(id,name,mimeType,modifiedTime,owners)",
            "orderBy": "folder,name",
        },
    )
    return [_format_file(f) for f in data.get("files", [])]


def get_recent(client: GoogleClient, days: int = 7, *, limit: int = 20) -> list[dict[str, Any]]:
    from datetime import UTC, datetime, timedelta

    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    q = f"modifiedTime > '{since}' and trashed = false"
    data = _get(
        client,
        "/files",
        params={
            "q": q,
            "pageSize": limit,
            "fields": "files(id,name,mimeType,modifiedTime,owners)",
            "orderBy": "modifiedTime desc",
        },
    )
    return [_format_file(f) for f in data.get("files", [])]


# --- Fetch ---


def fetch_file(
    client: GoogleClient,
    file_id: str,
    output_dir: Path,
    *,
    format_override: str | None = None,
) -> Path:
    """Fetch a file to output_dir. Returns the path of the written file."""
    meta = _get(client, f"/files/{file_id}", params={"fields": "id,name,mimeType"})
    name = meta.get("name", "untitled")
    mime = meta.get("mimeType", "")
    output_dir.mkdir(parents=True, exist_ok=True)

    if format_override and format_override in FORMAT_MIME:
        return _export_file(
            client, file_id, name, FORMAT_MIME[format_override], output_dir, format_override
        )

    google_type = GOOGLE_DOC_TYPES.get(mime)
    if google_type:
        export_mime = google_type["export"]
        ext = google_type["ext"]
        if export_mime == "text/html" and ext == ".md":
            return _export_as_markdown(client, file_id, name, output_dir)
        return _export_file(client, file_id, name, export_mime, output_dir, ext.lstrip("."))

    return _download_binary(client, file_id, name, output_dir)


def fetch_to_stdout(client: GoogleClient, file_id: str) -> str:
    """Fetch file content to string for stdout output."""
    meta = _get(client, f"/files/{file_id}", params={"fields": "id,name,mimeType"})
    mime = meta.get("mimeType", "")

    google_type = GOOGLE_DOC_TYPES.get(mime)
    if google_type:
        export_mime = google_type["export"]
        content = _download(client, f"{API_BASE}/files/{file_id}/export?mimeType={export_mime}")
        if export_mime == "text/html":
            from agent_kit.google.mail import html_to_markdown

            return html_to_markdown(content.decode("utf-8", errors="replace"))
        return content.decode("utf-8", errors="replace")

    raise ValueError(
        "binary files cannot be output to stdout — use --output or default file output"
    )


def _export_as_markdown(client: GoogleClient, file_id: str, name: str, output_dir: Path) -> Path:
    """Export Google Doc/Slides as HTML, convert to markdown via pandoc."""
    html = _download(client, f"{API_BASE}/files/{file_id}/export?mimeType=text/html")
    slug = _slugify(name)
    md_path = output_dir / f"{slug}.md"
    media_dir = output_dir / f"{slug}_media"

    try:
        result = subprocess.run(
            [
                "pandoc",
                "-f",
                "html",
                "-t",
                "markdown",
                "--wrap=none",
                f"--extract-media={media_dir}",
            ],
            input=html,
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0:
            md_path.write_bytes(result.stdout)
            if media_dir.exists() and not any(media_dir.iterdir()):
                media_dir.rmdir()
            return md_path
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    from agent_kit.google.mail import html_to_markdown

    md_path.write_text(html_to_markdown(html.decode("utf-8", errors="replace")))
    return md_path


def _export_file(
    client: GoogleClient,
    file_id: str,
    name: str,
    export_mime: str,
    output_dir: Path,
    ext: str,
) -> Path:
    """Export a Google Workspace file in the specified format."""
    content = _download(client, f"{API_BASE}/files/{file_id}/export?mimeType={export_mime}")
    slug = _slugify(name)
    path = output_dir / f"{slug}.{ext}"
    path.write_bytes(content)
    return path


def _download_binary(client: GoogleClient, file_id: str, name: str, output_dir: Path) -> Path:
    """Download a binary file directly."""
    content = _download(client, f"{API_BASE}/files/{file_id}?alt=media")
    path = output_dir / name
    path.write_bytes(content)
    return path


# --- Helpers ---


def _escape(value: str) -> str:
    """Escape a value for Drive query strings."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")
