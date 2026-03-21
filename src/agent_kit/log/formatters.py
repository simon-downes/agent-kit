"""Output formatters for activity log data."""

import json
from datetime import datetime
from sqlite3 import Row

from rich.console import Console

console = Console()


def format_human(entries: list[Row]) -> None:
    """Format entries in human-readable format."""
    if not entries:
        console.print("[dim]No entries found[/dim]")
        return

    for entry in entries:
        ts = datetime.fromisoformat(entry["ts"])
        ts_str = ts.strftime("%Y-%m-%d %H:%M")

        header = f"[dim]{ts_str}[/dim] [cyan]{entry['kind']}[/cyan]"
        header += f" [dim]({entry['project']})[/dim]"

        if entry["topic"]:
            header += f" | {entry['topic']}"

        console.print(header)

        if entry["ref"]:
            console.print(f"  [dim]Ref:[/dim] {entry['ref']}")

        console.print(f"  {entry['summary']}")
        console.print()


def format_json(entries: list[Row]) -> str:
    """Format entries as JSON."""
    data = [
        {
            "id": entry["id"],
            "ts": entry["ts"],
            "project": entry["project"],
            "kind": entry["kind"],
            "topic": entry["topic"],
            "ref": entry["ref"],
            "summary": entry["summary"],
            "metadata": entry["metadata"],
        }
        for entry in entries
    ]
    return json.dumps(data, indent=2)
