"""Output formatters for memory data."""

import json
from datetime import datetime
from sqlite3 import Row

from rich.console import Console

console = Console()


def format_human(memories: list[Row]) -> None:
    """Format memories in human-readable format."""
    if not memories:
        console.print("[dim]No memories found[/dim]")
        return

    for memory in memories:
        # Parse timestamp
        ts = datetime.fromisoformat(memory["ts"])
        ts_str = ts.strftime("%Y-%m-%d %H:%M")

        # Build header line
        header = f"[dim]{ts_str}[/dim] [cyan]{memory['kind']}[/cyan]"

        if memory["topic"]:
            header += f" | {memory['topic']}"

        console.print(header)

        # Show ref if present
        if memory["ref"]:
            console.print(f"  [dim]Ref:[/dim] {memory['ref']}")

        # Show summary
        console.print(f"  {memory['summary']}")
        console.print()


def format_json(memories: list[Row]) -> str:
    """Format memories as JSON."""
    data = [
        {
            "id": memory["id"],
            "ts": memory["ts"],
            "project": memory["project"],
            "kind": memory["kind"],
            "topic": memory["topic"],
            "ref": memory["ref"],
            "summary": memory["summary"],
            "metadata": memory["metadata"],
        }
        for memory in memories
    ]
    return json.dumps(data, indent=2)
