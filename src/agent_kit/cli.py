"""Main CLI entry point."""

import click

from agent_kit import __version__
from agent_kit.auth.cli import auth
from agent_kit.brain.cli import brain
from agent_kit.google.cli import google
from agent_kit.jira.cli import jira
from agent_kit.linear.cli import linear
from agent_kit.notion.cli import notion
from agent_kit.project import project
from agent_kit.slack.cli import slack
from agent_kit.tasks.cli import tasks


@click.group()
@click.version_option(version=__version__, prog_name="agent-kit")
def main() -> None:
    """Agent Kit — CLI toolkit for AI agent capabilities."""


main.add_command(auth)
main.add_command(brain)
main.add_command(google)
main.add_command(jira)
main.add_command(linear)
main.add_command(notion)
main.add_command(project)
main.add_command(slack)
main.add_command(tasks)
