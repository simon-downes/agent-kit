"""Project name command."""

from pathlib import Path

import click

from agent_kit.project import resolve_project


@click.command()
@click.argument("path", required=False, type=click.Path(exists=True, path_type=Path))
def main(path: Path | None = None) -> None:
    """Display the project name for a directory.

    If PATH is not provided, uses the current directory.
    """
    if path is None:
        path = Path.cwd()

    project_name = resolve_project(cwd=path)
    click.echo(project_name)
