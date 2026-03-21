"""CLI interface for activity log."""

import sys

import click
from rich.console import Console

from agent_kit.log import db
from agent_kit.log.models import validate_kebab_case, validate_kind, validate_metadata
from agent_kit.project import resolve_project

console = Console()


@click.group()
def main() -> None:
    """Log - Activity log for development workflows."""
    pass


@main.command("add")
@click.option("--project", help="Project name (auto-detected if not provided)")
@click.option("--kind", required=True, help="Entry kind")
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
    """Add a log entry."""
    try:
        if summary == "-":
            summary = sys.stdin.read()

        summary = summary.strip()

        if not summary:
            console.print("[red]Error:[/red] Summary cannot be empty")
            sys.exit(1)

        if not project:
            project = resolve_project()

        validate_kebab_case(project)
        validate_kind(kind)

        if topic:
            validate_kebab_case(topic)

        validate_metadata(metadata)

        entry_id = db.add_entry(
            project=project,
            kind=kind,
            summary=summary,
            topic=topic,
            ref=ref,
            metadata=metadata,
        )

        console.print(f"[green]Added entry {entry_id}[/green]")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command("list")
@click.option("--project", help="Project name (omit for cross-project query)")
@click.option(
    "--limit",
    default=25,
    type=int,
    help="Maximum number of results (default: 25, max: 100)",
)
@click.option("--kind", help="Filter by entry kind")
@click.option("--topic", help="Filter by topic")
@click.option("--since", help="Only entries on or after date (ISO or relative, e.g. 7d, 4w)")
@click.option("--until", help="Only entries on or before date (ISO or relative, e.g. 7d, 4w)")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def list_cmd(
    project: str | None,
    limit: int,
    kind: str | None,
    topic: str | None,
    since: str | None,
    until: str | None,
    json_output: bool,
) -> None:
    """List log entries."""
    try:
        if limit > 100:
            limit = 100
        elif limit < 1:
            limit = 1

        if kind:
            validate_kind(kind)

        if topic:
            validate_kebab_case(topic)

        entries = db.list_entries(
            project=project,
            kind=kind,
            topic=topic,
            since=since,
            until=until,
            limit=limit,
        )

        if json_output:
            from agent_kit.log.formatters import format_json

            print(format_json(entries))
        else:
            from agent_kit.log.formatters import format_human

            format_human(entries)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command("stats")
@click.option("--project", help="Project name (omit for cross-project stats)")
def stats_cmd(project: str | None) -> None:
    """Show activity statistics."""
    from rich.table import Table

    stats = db.get_stats(project)

    if not stats["activity"]["total"]:
        label = f"project '{project}'" if project else "any project"
        console.print(f"[dim]No entries found for {label}[/dim]")
        return

    title = f"Activity Statistics: {project}" if project else "Activity Statistics: All Projects"
    console.print(f"\n[bold]{title}[/bold]\n")
    console.print(f"Total entries: {stats['activity']['total']}")
    console.print(f"Last 7 days: {stats['activity']['last_7_days']}")
    console.print(f"Last 30 days: {stats['activity']['last_30_days']}")

    if stats["by_kind"]:
        console.print("\n[bold]By Kind:[/bold]\n")
        table = Table(show_header=True)
        table.add_column("Kind")
        table.add_column("Count", justify="right")
        for kind, count in stats["by_kind"].items():
            table.add_row(kind, str(count))
        console.print(table)

    if stats["by_project"]:
        console.print("\n[bold]By Project:[/bold]\n")
        table = Table(show_header=True)
        table.add_column("Project")
        table.add_column("Count", justify="right")
        for proj, count in stats["by_project"].items():
            table.add_row(proj, str(count))
        console.print(table)


if __name__ == "__main__":
    main()
