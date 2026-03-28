"""Main CLI entry point."""

import click

from agent_kit import __version__
from agent_kit.notion.cli import notion


@click.group()
@click.version_option(version=__version__, prog_name="agent-kit")
def main() -> None:
    """Agent Kit — CLI toolkit for AI agent capabilities."""


main.add_command(notion)
