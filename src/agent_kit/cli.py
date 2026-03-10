"""Main CLI entry point for agent-kit."""

import click

from agent_kit.kv.cli import main as kv_cli
from agent_kit.oauth.cli import main as oauth_cli
from agent_kit.notion.cli import main as notion_cli


@click.group()
def main() -> None:
    """Agent Kit - Unified CLI tools for development workflows."""
    pass


main.add_command(kv_cli, name="kv")
main.add_command(oauth_cli, name="oauth")
main.add_command(notion_cli, name="notion")


if __name__ == "__main__":
    main()
