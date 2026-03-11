"""Main CLI entry point for agent-kit."""

import click

from agent_kit.check.cli import main as check_cli
from agent_kit.commands.project import main as project_cli
from agent_kit.kv.cli import main as kv_cli
from agent_kit.mem.cli import main as mem_cli
from agent_kit.notion.cli import main as notion_cli
from agent_kit.oauth.cli import main as oauth_cli


@click.group()
def main() -> None:
    """Agent Kit - Unified CLI tools for development workflows."""
    pass


main.add_command(check_cli, name="check")
main.add_command(kv_cli, name="kv")
main.add_command(mem_cli, name="mem")
main.add_command(oauth_cli, name="oauth")
main.add_command(notion_cli, name="notion")
main.add_command(project_cli, name="project")


if __name__ == "__main__":
    main()
