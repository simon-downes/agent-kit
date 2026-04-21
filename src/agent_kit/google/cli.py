"""Google Workspace CLI subcommands."""

import click

from agent_kit.config import load_config
from agent_kit.errors import ConfigError, handle_errors, output


def require_service(service: str) -> None:
    """Check that a Google service is enabled in config."""
    config = load_config()
    enabled = config.get("google", {}).get(service, {}).get("enabled", True)
    if not enabled:
        raise ConfigError(f"Google {service} is disabled in config")


def _get_client():
    """Create a GoogleClient from the credential store."""
    from agent_kit.auth import get_field
    from agent_kit.google.client import GoogleClient

    fields = ("access_token", "expires_at", "refresh_token", "client_id", "client_secret")
    creds = {f: get_field("google", f) for f in fields}
    return GoogleClient(creds)


def _resolve_inbox() -> str:
    """Resolve the brain raw inbox path from config."""
    from pathlib import Path

    config = load_config()
    brain_dir = config.get("brain", {}).get("dir", "~/.archie/brain")
    inbox = Path(brain_dir).expanduser() / "_raw" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    return str(inbox)


@click.group()
def google() -> None:
    """Google Workspace — Gmail, Calendar, and Drive."""


# --- Mail ---


@google.group()
def mail() -> None:
    """Gmail — search, read, and download emails."""


@mail.command()
@click.argument("query")
@click.option("--limit", default=20, help="Maximum results")
@handle_errors
def search(query: str, limit: int) -> None:
    """Search emails using Gmail query syntax."""
    require_service("mail")
    output(_get_client().mail_search(query, limit=limit))


@mail.command()
@click.option("--hours", default=24, help="Hours to look back (default: 24)")
@click.option("--limit", default=20, help="Maximum results")
@handle_errors
def recent(hours: int, limit: int) -> None:
    """List recent emails."""
    require_service("mail")
    output(_get_client().mail_recent(hours, limit=limit))


@mail.command()
@click.option("--limit", default=20, help="Maximum results")
@handle_errors
def unread(limit: int) -> None:
    """List unread emails."""
    require_service("mail")
    output(_get_client().mail_unread(limit=limit))


@mail.command("read")
@click.argument("message_id")
@click.option("--stdout", "to_stdout", is_flag=True, help="Output body to stdout instead of file")
@click.option("--to-inbox", "to_inbox", is_flag=True, help="Write to brain raw inbox")
@click.option("--output", "output_dir", help="Output directory")
@handle_errors
def read_cmd(message_id: str, to_stdout: bool, to_inbox: bool, output_dir: str | None) -> None:
    """Read an email by ID. Downloads as markdown with attachments."""
    require_service("mail")
    from pathlib import Path

    client = _get_client()

    if to_stdout:
        msg = client.mail_read(message_id)
        print(msg["body"])
        return

    if to_inbox:
        out = Path(_resolve_inbox())
    elif output_dir:
        out = Path(output_dir)
    else:
        out = Path(".")

    md_path, att_paths = client.mail_download(message_id, out)
    result = {"file": str(md_path)}
    if att_paths:
        result["attachments"] = [str(p) for p in att_paths]
    output(result)


# --- Calendar ---


@google.group()
def calendar() -> None:
    """Google Calendar — events and schedules."""


@calendar.command()
@handle_errors
def today() -> None:
    """List today's events."""
    require_service("calendar")
    output(_get_client().calendar_today())


@calendar.command()
@click.option("--days", default=7, help="Number of days ahead (default: 7)")
@handle_errors
def upcoming(days: int) -> None:
    """List upcoming events."""
    require_service("calendar")
    output(_get_client().calendar_upcoming(days))


@calendar.command()
@click.argument("event_id")
@handle_errors
def event(event_id: str) -> None:
    """Get event details."""
    require_service("calendar")
    output(_get_client().calendar_event(event_id))


# --- Drive ---


@google.group()
def drive() -> None:
    """Google Drive — search, list, and fetch files."""


@drive.command("search")
@click.argument("query")
@click.option("--limit", default=20, help="Maximum results")
@handle_errors
def drive_search(query: str, limit: int) -> None:
    """Search files by name or content."""
    require_service("drive")
    output(_get_client().drive_search(query, limit=limit))


@drive.command("recent")
@click.option("--days", default=7, help="Days to look back (default: 7)")
@click.option("--limit", default=20, help="Maximum results")
@handle_errors
def drive_recent(days: int, limit: int) -> None:
    """List recently modified files."""
    require_service("drive")
    output(_get_client().drive_recent(days, limit=limit))


@drive.command("list")
@click.option("--folder", "folder_id", help="Folder ID to list")
@click.option("--limit", default=50, help="Maximum results")
@handle_errors
def list_cmd(folder_id: str | None, limit: int) -> None:
    """List folder contents."""
    require_service("drive")
    output(_get_client().drive_list(folder_id=folder_id, limit=limit))


@drive.command()
@click.argument("file_id")
@click.option("--stdout", "to_stdout", is_flag=True, help="Output content to stdout")
@click.option("--to-inbox", "to_inbox", is_flag=True, help="Write to brain raw inbox")
@click.option("--output", "output_dir", help="Output directory")
@click.option("--format", "fmt", help="Export format (html, pdf, csv, text)")
@handle_errors
def fetch(
    file_id: str, to_stdout: bool, to_inbox: bool, output_dir: str | None, fmt: str | None
) -> None:
    """Fetch a file. Google Docs export as markdown, binary files download as-is."""
    require_service("drive")
    from pathlib import Path

    client = _get_client()

    if to_stdout:
        print(client.drive_fetch_stdout(file_id))
        return

    if to_inbox:
        out = Path(_resolve_inbox())
    elif output_dir:
        out = Path(output_dir)
    else:
        out = Path(".")

    path = client.drive_fetch(file_id, out, format_override=fmt)
    output({"file": str(path)})
