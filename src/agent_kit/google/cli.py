"""Google Workspace CLI subcommands."""

import click

from agent_kit.errors import handle_errors, output
from agent_kit.google.auth import require_service
from agent_kit.google.calendar import get_event, get_today, get_upcoming


def _resolve_inbox() -> str:
    """Resolve the brain raw inbox path from config."""
    from pathlib import Path

    from agent_kit.config import load_config

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
    from agent_kit.google.mail import search_messages

    output(search_messages(query, limit=limit))


@mail.command()
@click.option("--hours", default=24, help="Hours to look back (default: 24)")
@click.option("--limit", default=20, help="Maximum results")
@handle_errors
def recent(hours: int, limit: int) -> None:
    """List recent emails."""
    require_service("mail")
    from agent_kit.google.mail import list_recent

    output(list_recent(hours, limit=limit))


@mail.command()
@click.option("--limit", default=20, help="Maximum results")
@handle_errors
def unread(limit: int) -> None:
    """List unread emails."""
    require_service("mail")
    from agent_kit.google.mail import list_unread

    output(list_unread(limit=limit))


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

    from agent_kit.google.mail import get_message, write_message_to_file

    if to_stdout:
        msg = get_message(message_id)
        print(msg["body"])
        return

    if to_inbox:
        out = Path(_resolve_inbox())
    elif output_dir:
        out = Path(output_dir)
    else:
        out = Path(".")

    md_path, att_paths = write_message_to_file(message_id, out)
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
    output(get_today())


@calendar.command()
@click.option("--days", default=7, help="Number of days ahead (default: 7)")
@handle_errors
def upcoming(days: int) -> None:
    """List upcoming events."""
    require_service("calendar")
    output(get_upcoming(days))


@calendar.command()
@click.argument("event_id")
@handle_errors
def event(event_id: str) -> None:
    """Get event details."""
    require_service("calendar")
    output(get_event(event_id))


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
    from agent_kit.google.drive import search_files

    output(search_files(query, limit=limit))


@drive.command("recent")
@click.option("--days", default=7, help="Days to look back (default: 7)")
@click.option("--limit", default=20, help="Maximum results")
@handle_errors
def drive_recent(days: int, limit: int) -> None:
    """List recently modified files."""
    require_service("drive")
    from agent_kit.google.drive import get_recent

    output(get_recent(days, limit=limit))


@drive.command("list")
@click.option("--folder", "folder_id", help="Folder ID to list")
@click.option("--limit", default=50, help="Maximum results")
@handle_errors
def list_cmd(folder_id: str | None, limit: int) -> None:
    """List folder contents."""
    require_service("drive")
    from agent_kit.google.drive import list_files

    output(list_files(folder_id=folder_id, limit=limit))


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

    from agent_kit.google.drive import fetch_file, fetch_to_stdout

    if to_stdout:
        print(fetch_to_stdout(file_id))
        return

    if to_inbox:
        out = Path(_resolve_inbox())
    elif output_dir:
        out = Path(output_dir)
    else:
        out = Path(".")

    path = fetch_file(file_id, out, format_override=fmt)
    output({"file": str(path)})
