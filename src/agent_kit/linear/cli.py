"""Linear CLI subcommands."""

import os
import sys

import click

from agent_kit.errors import AuthError, handle_errors, output
from agent_kit.linear.client import LinearClient
from agent_kit.linear.resolve import (
    resolve_assignee,
    resolve_labels,
    resolve_status,
    resolve_team_id,
)


def _get_client() -> LinearClient:
    """Get a LinearClient from credential store or environment."""
    from agent_kit.auth import get_field

    key = get_field("linear", "token") or os.environ.get("LINEAR_TOKEN")
    if not key:
        raise AuthError("no Linear credentials — run 'ak auth set linear token'")
    return LinearClient(key)


@click.group()
def linear() -> None:
    """Linear — issue tracking and project management."""


@linear.command()
@handle_errors
def teams() -> None:
    """List all teams."""
    output(_get_client().get_teams())


@linear.command()
@click.argument("id_or_key")
@handle_errors
def team(id_or_key: str) -> None:
    """Get team details including workflow states."""
    output(_get_client().get_team(id_or_key))


@linear.command()
@click.option("--team", "team_key", help="Filter by team key")
@handle_errors
def projects(team_key: str | None) -> None:
    """List projects."""
    output(_get_client().get_projects(team_key=team_key))


def _resolve_filters(
    client: LinearClient, team_key: str, **kwargs: str | None
) -> dict[str, str | None]:
    """Resolve friendly names to IDs for issue filtering."""
    result: dict[str, str | None] = {"team_id": resolve_team_id(client, team_key)}
    if kwargs.get("status"):
        result["status_id"] = resolve_status(client, team_key, kwargs["status"])
    if kwargs.get("assignee"):
        result["assignee_id"] = resolve_assignee(client, team_key, kwargs["assignee"])
    if kwargs.get("label"):
        ids = resolve_labels(client, team_key, [kwargs["label"]])
        result["label_id"] = ids[0]
    return result


@linear.command()
@click.option("--team", "team_key", required=True, help="Team key (e.g. PLAT)")
@click.option("--status", help="Filter by status name")
@click.option("--assignee", help="Filter by assignee name")
@click.option("--label", help="Filter by label name")
@click.option("--project", "project_name", help="Filter by project name")
@click.option("--created-after", help="Created on or after date (YYYY-MM-DD)")
@click.option("--created-before", help="Created on or before date (YYYY-MM-DD)")
@click.option("--updated-after", help="Updated on or after date (YYYY-MM-DD)")
@click.option("--updated-before", help="Updated on or before date (YYYY-MM-DD)")
@click.option("--limit", default=50, help="Maximum results")
@handle_errors
def issues(
    team_key: str,
    status: str | None,
    assignee: str | None,
    label: str | None,
    project_name: str | None,
    created_after: str | None,
    created_before: str | None,
    updated_after: str | None,
    updated_before: str | None,
    limit: int,
) -> None:
    """List issues for a team."""
    client = _get_client()
    resolved = _resolve_filters(client, team_key, status=status, assignee=assignee, label=label)

    output(
        client.get_issues(
            team_id=resolved["team_id"],
            status_id=resolved.get("status_id"),
            assignee_id=resolved.get("assignee_id"),
            label_id=resolved.get("label_id"),
            project_name=project_name,
            created_after=created_after,
            created_before=created_before,
            updated_after=updated_after,
            updated_before=updated_before,
            limit=limit,
        )
    )


@linear.command()
@click.argument("identifier")
@handle_errors
def issue(identifier: str) -> None:
    """Get issue details by identifier (e.g. PLAT-123)."""
    output(_get_client().get_issue(identifier))


@linear.command("create-issue")
@click.option("--team", "team_key", required=True, help="Team key (e.g. PLAT)")
@click.option("--title", required=True, help="Issue title")
@click.option("--description", help="Issue description (or pipe via stdin)")
@click.option("--status", help="Status name")
@click.option("--assignee", help="Assignee name")
@click.option("--priority", type=click.IntRange(1, 4), help="Priority (1=urgent, 4=low)")
@click.option("--label", "labels", multiple=True, help="Label name (repeatable)")
@handle_errors
def create_issue_cmd(
    team_key: str,
    title: str,
    description: str | None,
    status: str | None,
    assignee: str | None,
    priority: int | None,
    labels: tuple[str, ...],
) -> None:
    """Create a new issue."""
    client = _get_client()

    if not description and not sys.stdin.isatty():
        description = sys.stdin.read().strip() or None

    team_id = resolve_team_id(client, team_key)
    state_id = resolve_status(client, team_key, status) if status else None
    assignee_id = resolve_assignee(client, team_key, assignee) if assignee else None
    label_ids = resolve_labels(client, team_key, list(labels)) if labels else None

    output(
        client.create_issue(
            team_id=team_id,
            title=title,
            description=description,
            state_id=state_id,
            assignee_id=assignee_id,
            priority=priority,
            label_ids=label_ids,
        )
    )


@linear.command("update-issue")
@click.argument("identifier")
@click.option("--title", help="New title")
@click.option("--description", help="New description (or pipe via stdin)")
@click.option("--status", help="Status name")
@click.option("--assignee", help="Assignee name")
@click.option("--priority", type=click.IntRange(1, 4), help="Priority (1=urgent, 4=low)")
@click.option("--label", "labels", multiple=True, help="Label name (repeatable, replaces all)")
@handle_errors
def update_issue_cmd(
    identifier: str,
    title: str | None,
    description: str | None,
    status: str | None,
    assignee: str | None,
    priority: int | None,
    labels: tuple[str, ...],
) -> None:
    """Update an issue."""
    client = _get_client()

    if not description and not sys.stdin.isatty():
        description = sys.stdin.read().strip() or None

    # Need team context for name resolution
    team_key: str | None = None
    if status or assignee or labels:
        detail = client.get_issue(identifier)
        team_key = detail.get("team")
        if not team_key:
            raise ValueError("could not determine team for issue")

    state_id = resolve_status(client, team_key, status) if status and team_key else None
    assignee_id = resolve_assignee(client, team_key, assignee) if assignee and team_key else None
    label_ids = resolve_labels(client, team_key, list(labels)) if labels and team_key else None

    output(
        client.update_issue(
            identifier,
            title=title,
            description=description,
            state_id=state_id,
            assignee_id=assignee_id,
            priority=priority,
            label_ids=label_ids,
        )
    )


@linear.command()
@click.argument("identifier")
@handle_errors
def comments(identifier: str) -> None:
    """List comments on an issue."""
    output(_get_client().get_comments(identifier))


@linear.command("comment")
@click.argument("identifier")
@click.option("--message", "-m", help="Comment body")
@handle_errors
def comment_cmd(identifier: str, message: str | None) -> None:
    """Add a comment to an issue."""
    if not message:
        if sys.stdin.isatty():
            raise ValueError("provide --message or pipe content via stdin")
        message = sys.stdin.read().strip()

    if not message:
        raise ValueError("empty comment message")

    output(_get_client().create_comment(identifier, body=message))


@linear.command()
@click.argument("file_path", type=click.Path(exists=True))
@handle_errors
def upload(file_path: str) -> None:
    """Upload a file to Linear's storage."""
    output(_get_client().upload_file(file_path))
