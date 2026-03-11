"""CLI interface for mem tool."""

import sys

import click
from rich.console import Console

from agent_kit.mem import db
from agent_kit.mem.models import validate_kebab_case, validate_kind, validate_metadata
from agent_kit.project import resolve_project

console = Console()


@click.group()
def main() -> None:
    """Mem - Agent memory storage and retrieval."""
    pass


@main.command("add")
@click.option("--project", help="Project name (auto-detected if not provided)")
@click.option("--kind", required=True, help="Memory kind")
@click.option("--topic", help="Optional topic in lower-kebab-case")
@click.option("--ref", help="Optional reference (commit, PR, issue)")
@click.option("--metadata", default="", help="Optional JSON metadata")
@click.argument("summary")
def add_cmd(
    project: str | None,
    kind: str,
    topic: str | None,
    ref: str | None,
    metadata: str,
    summary: str,
) -> None:
    """Add a memory."""
    try:
        # Read from stdin if summary is "-"
        if summary == "-":
            summary = sys.stdin.read()

        # Strip leading/trailing whitespace
        summary = summary.strip()

        if not summary:
            console.print("[red]Error:[/red] Summary cannot be empty")
            sys.exit(1)

        # Resolve project if not provided
        if not project:
            project = resolve_project()

        # Validate inputs
        validate_kebab_case(project)
        validate_kind(kind)

        if topic:
            validate_kebab_case(topic)

        validate_metadata(metadata)

        # Add to database
        memory_id = db.add_memory(
            project=project,
            kind=kind,
            summary=summary,
            topic=topic,
            ref=ref,
            metadata=metadata,
        )

        console.print(f"[green]Added memory {memory_id}[/green]")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command("list")
@click.option("--project", help="Project name (auto-detected if not provided)")
@click.option(
    "--limit",
    default=25,
    type=int,
    help="Maximum number of results (default: 25, max: 100)",
)
@click.option("--kind", help="Filter by memory kind")
@click.option("--topic", help="Filter by topic")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def list_cmd(
    project: str | None,
    limit: int,
    kind: str | None,
    topic: str | None,
    json_output: bool,
) -> None:
    """List memories for a project."""
    try:
        # Resolve project if not provided
        if not project:
            project = resolve_project()

        # Validate and enforce limit
        if limit > 100:
            limit = 100
        elif limit < 1:
            limit = 1

        # Validate filters
        if kind:
            validate_kind(kind)

        if topic:
            validate_kebab_case(topic)

        # Query database
        memories = db.list_memories(
            project=project,
            kind=kind,
            topic=topic,
            limit=limit,
        )

        if json_output:
            from agent_kit.mem.formatters import format_json
            print(format_json(memories))
        else:
            from agent_kit.mem.formatters import format_human
            format_human(memories)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command("stats")
@click.option("--project", help="Project name (auto-detected if not provided)")
def stats_cmd(project: str | None) -> None:
    """Show statistics for a project."""
    from rich.table import Table

    # Resolve project if not provided
    if not project:
        project = resolve_project()

    stats = db.get_stats(project)

    if not stats["activity"]["total"]:
        console.print(f"[dim]No memories found for project '{project}'[/dim]")
        return

    # Activity summary
    console.print(f"\n[bold]Memory Statistics: {project}[/bold]\n")
    console.print(f"Total memories: {stats['activity']['total']}")
    console.print(f"Last 7 days: {stats['activity']['last_7_days']}")
    console.print(f"Last 30 days: {stats['activity']['last_30_days']}")

    # Count by kind
    if stats["by_kind"]:
        console.print("\n[bold]By Kind:[/bold]\n")
        table = Table(show_header=True)
        table.add_column("Kind")
        table.add_column("Count", justify="right")

        for kind, count in stats["by_kind"].items():
            table.add_row(kind, str(count))

        console.print(table)


if __name__ == "__main__":
    main()
