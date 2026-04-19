"""Jira CLI subcommands."""

import os
import sys

import click

from agent_kit.errors import AuthError, handle_errors, output
from agent_kit.jira.client import (
    JiraClient,
    attach_file,
    create_comment,
    create_issue,
    get_comments,
    get_issue,
    get_project,
    get_projects,
    get_statuses,
    search_issues,
    transition_issue,
    update_issue,
)
from agent_kit.jira.resolve import resolve_assignee, resolve_transition


def _get_client() -> JiraClient:
    """Get a JiraClient from credential store or environment."""
    from agent_kit.auth import get_field

    email = get_field("jira", "email") or os.environ.get("JIRA_EMAIL")
    token = get_field("jira", "token") or os.environ.get("JIRA_TOKEN")
    cloud_id = get_field("jira", "cloud_id") or os.environ.get("JIRA_CLOUD_ID")

    if not email or not token or not cloud_id:
        missing = []
        if not email:
            missing.append("email")
        if not token:
            missing.append("token")
        if not cloud_id:
            missing.append("cloud_id")
        raise AuthError(
            f"missing Jira credentials ({', '.join(missing)}) — "
            "run 'ak auth set jira email/token/cloud_id'"
        )
    return JiraClient(email, token, cloud_id)


@click.group()
def jira() -> None:
    """Jira — issue tracking and project management."""


@jira.command()
@click.option("--limit", default=50, help="Maximum results")
@handle_errors
def projects(limit: int) -> None:
    """List projects."""
    output(get_projects(_get_client(), limit=limit))


@jira.command()
@click.argument("key_or_id")
@handle_errors
def project(key_or_id: str) -> None:
    """Get project details including issue types."""
    output(get_project(_get_client(), key_or_id))


@jira.command()
@click.argument("project_key")
@handle_errors
def statuses(project_key: str) -> None:
    """List statuses for a project, grouped by issue type."""
    output(get_statuses(_get_client(), project_key))


@jira.command()
@click.option("--project", "project_key", help="Filter by project key")
@click.option("--status", help="Filter by status name")
@click.option("--assignee", help="Filter by assignee name")
@click.option("--type", "issue_type", help="Filter by issue type (Bug, Task, Story, etc.)")
@click.option("--label", help="Filter by label")
@click.option("--created-after", help="Created on or after date (YYYY-MM-DD)")
@click.option("--created-before", help="Created on or before date (YYYY-MM-DD)")
@click.option("--updated-after", help="Updated on or after date (YYYY-MM-DD)")
@click.option("--updated-before", help="Updated on or before date (YYYY-MM-DD)")
@click.option("--jql", help="Raw JQL query (overrides other filters)")
@click.option("--limit", default=50, help="Maximum results")
@handle_errors
def issues(
    project_key: str | None,
    status: str | None,
    assignee: str | None,
    issue_type: str | None,
    label: str | None,
    created_after: str | None,
    created_before: str | None,
    updated_after: str | None,
    updated_before: str | None,
    jql: str | None,
    limit: int,
) -> None:
    """Search issues with filters or JQL."""
    output(
        search_issues(
            _get_client(),
            jql=jql,
            project=project_key,
            status=status,
            assignee=assignee,
            issue_type=issue_type,
            label=label,
            created_after=created_after,
            created_before=created_before,
            updated_after=updated_after,
            updated_before=updated_before,
            limit=limit,
        )
    )


@jira.command()
@click.argument("key")
@handle_errors
def issue(key: str) -> None:
    """Get issue details by key (e.g. PLAT-123)."""
    output(get_issue(_get_client(), key))


@jira.command("create-issue")
@click.option("--project", "project_key", required=True, help="Project key (e.g. PLAT)")
@click.option("--summary", required=True, help="Issue summary")
@click.option("--type", "issue_type", required=True, help="Issue type (Bug, Task, Story, etc.)")
@click.option("--description", help="Issue description (or pipe via stdin)")
@click.option("--priority", help="Priority name (e.g. High, Medium, Low)")
@click.option("--assignee", help="Assignee name")
@click.option("--label", "labels", multiple=True, help="Label (repeatable)")
@handle_errors
def create_issue_cmd(
    project_key: str,
    summary: str,
    issue_type: str,
    description: str | None,
    priority: str | None,
    assignee: str | None,
    labels: tuple[str, ...],
) -> None:
    """Create a new issue."""
    client = _get_client()

    if not description and not sys.stdin.isatty():
        description = sys.stdin.read().strip() or None

    assignee_id = resolve_assignee(client, assignee) if assignee else None

    output(
        create_issue(
            client,
            project_key=project_key,
            summary=summary,
            issue_type=issue_type,
            description=description,
            priority=priority,
            labels=list(labels) if labels else None,
            assignee_id=assignee_id,
        )
    )


@jira.command("update-issue")
@click.argument("key")
@click.option("--summary", help="New summary")
@click.option("--description", help="New description (or pipe via stdin)")
@click.option("--priority", help="Priority name")
@click.option("--assignee", help="Assignee name")
@click.option("--label", "labels", multiple=True, help="Label (repeatable, replaces all)")
@handle_errors
def update_issue_cmd(
    key: str,
    summary: str | None,
    description: str | None,
    priority: str | None,
    assignee: str | None,
    labels: tuple[str, ...],
) -> None:
    """Update an issue."""
    client = _get_client()

    if not description and not sys.stdin.isatty():
        description = sys.stdin.read().strip() or None

    assignee_id = resolve_assignee(client, assignee) if assignee else None

    output(
        update_issue(
            client,
            key,
            summary=summary,
            description=description,
            priority=priority,
            labels=list(labels) if labels else None,
            assignee_id=assignee_id,
        )
    )


@jira.command()
@click.argument("key")
@click.option("--status", required=True, help="Target status name")
@handle_errors
def transition(key: str, status: str) -> None:
    """Transition an issue to a new status."""
    client = _get_client()
    transition_id = resolve_transition(client, key, status)
    output(transition_issue(client, key, transition_id=transition_id))


@jira.command()
@click.argument("key")
@handle_errors
def comments(key: str) -> None:
    """List comments on an issue."""
    output(get_comments(_get_client(), key))


@jira.command("comment")
@click.argument("key")
@click.option("--message", "-m", help="Comment body")
@handle_errors
def comment_cmd(key: str, message: str | None) -> None:
    """Add a comment to an issue."""
    if not message:
        if sys.stdin.isatty():
            raise ValueError("provide --message or pipe content via stdin")
        message = sys.stdin.read().strip()

    if not message:
        raise ValueError("empty comment message")

    output(create_comment(_get_client(), key, body=message))


@jira.command()
@click.argument("key")
@click.argument("file_path", type=click.Path(exists=True))
@handle_errors
def attach(key: str, file_path: str) -> None:
    """Attach a file to an issue."""
    output(attach_file(_get_client(), key, file_path))
