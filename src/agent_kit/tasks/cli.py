"""Task runner CLI subcommands."""

import sys

import click

from agent_kit.errors import handle_errors, output
from agent_kit.tasks.client import TaskClient, parse_duration


def _get_client() -> TaskClient:
    """Get a TaskClient with default database path."""
    return TaskClient()


@click.group()
def tasks() -> None:
    """Tasks — background task runner."""


@tasks.command()
@click.option("--name", required=True, help="Task name (must be unique among active tasks)")
@click.argument("cmd", nargs=-1, required=True)
@handle_errors
def create(name: str, cmd: tuple[str, ...]) -> None:
    """Create a pending task. Command and args follow after --."""
    command, *args = cmd
    task = _get_client().create(name, command, args)
    output(task["id"])


@tasks.command("list")
@click.option("--status", "status_filter", help="Filter by status")
@click.option("--all", "show_all", is_flag=True, help="Show all tasks (not just active)")
@click.option("--limit", default=20, help="Maximum results")
@handle_errors
def list_cmd(status_filter: str | None, show_all: bool, limit: int) -> None:
    """List tasks. Default shows pending and running only."""
    output(_get_client().list_tasks(status=status_filter, show_all=show_all, limit=limit))


@tasks.command()
@click.argument("name_or_id")
@handle_errors
def status(name_or_id: str) -> None:
    """Get task details by name or ID."""
    client = _get_client()
    task = client.get(name_or_id)
    log_path = client._log_path(task)
    if log_path.exists():
        task["log_file"] = str(log_path)
    output(task)


@tasks.command()
@click.argument("name_or_id")
@click.option("--error", is_flag=True, help="Show error (stderr) log instead of stdout")
@handle_errors
def log(name_or_id: str, error: bool) -> None:
    """Show task log output."""
    path = _get_client().get_log_path(name_or_id, error=error)
    if not path.exists():
        kind = "error log" if error else "log"
        raise FileNotFoundError(f"no {kind} file for task '{name_or_id}'")
    print(path.read_text(), end="")


@tasks.command()
@click.argument("name_or_id")
@handle_errors
def cancel(name_or_id: str) -> None:
    """Cancel a pending or running task."""
    task = _get_client().cancel(name_or_id)
    print(f"Cancelled task '{task['name']}'")


@tasks.command()
@handle_errors
def run() -> None:
    """Execute pending tasks. Intended as a cron entry point."""
    results = _get_client().run()
    if results:
        for task in results:
            print(f"[{task['status']}] {task['name']}", file=sys.stderr)


@tasks.command()
@click.option("--before", default="7d", help="Remove tasks older than this (e.g. 7d, 2h, 30m)")
@handle_errors
def clean(before: str) -> None:
    """Remove old completed tasks and their logs."""
    duration = parse_duration(before)
    count = _get_client().clean(duration)
    print(f"Removed {count} task(s)")
