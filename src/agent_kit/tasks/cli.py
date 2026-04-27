"""Task runner CLI subcommands."""

import click

from agent_kit.errors import handle_errors, output
from agent_kit.tasks.client import TaskClient


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
