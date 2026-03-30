"""Linear CLI subcommands."""

import json
import os
import sys
from typing import Any

import click

from agent_kit.linear.client import (
    LinearClient,
    create_comment,
    create_issue,
    get_comments,
    get_issue,
    get_issues,
    get_projects,
    get_team,
    get_teams,
    update_issue,
    upload_file,
)
from agent_kit.linear.resolve import (
    resolve_assignee,
    resolve_labels,
    resolve_status,
    resolve_team_id,
)


def _get_client() -> LinearClient:
    """Get a LinearClient or exit if no API key."""
    key = os.environ.get("LINEAR_TOKEN")
    if not key:
        print("Error: LINEAR_TOKEN environment variable is not set", file=sys.stderr)
        sys.exit(2)
    return LinearClient(key)


def _output(data: Any) -> None:
    """Write JSON to stdout."""
    print(json.dumps(data, indent=2))


@click.group()
def linear() -> None:
    """Linear — issue tracking and project management."""


@linear.command()
def teams() -> None:
    """List all teams."""
    _output(get_teams(_get_client()))


@linear.command()
@click.argument("id_or_key")
def team(id_or_key: str) -> None:
    """Get team details including workflow states."""
    _output(get_team(_get_client(), id_or_key))


@linear.command()
@click.option("--team", "team_key", help="Filter by team key")
def projects(team_key: str | None) -> None:
    """List projects."""
    _output(get_projects(_get_client(), team_key=team_key))


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
@click.option("--limit", default=50, help="Maximum results")
def issues(
    team_key: str,
    status: str | None,
    assignee: str | None,
    label: str | None,
    project_name: str | None,
    limit: int,
) -> None:
    """List issues for a team."""
    client = _get_client()
    try:
        resolved = _resolve_filters(client, team_key, status=status, assignee=assignee, label=label)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    _output(
        get_issues(
            client,
            team_id=resolved["team_id"],
            status_id=resolved.get("status_id"),
            assignee_id=resolved.get("assignee_id"),
            label_id=resolved.get("label_id"),
            project_name=project_name,
            limit=limit,
        )
    )


@linear.command()
@click.argument("identifier")
def issue(identifier: str) -> None:
    """Get issue details by identifier (e.g. PLAT-123)."""
    _output(get_issue(_get_client(), identifier))


@linear.command("create-issue")
@click.option("--team", "team_key", required=True, help="Team key (e.g. PLAT)")
@click.option("--title", required=True, help="Issue title")
@click.option("--description", help="Issue description (or pipe via stdin)")
@click.option("--status", help="Status name")
@click.option("--assignee", help="Assignee name")
@click.option("--priority", type=click.IntRange(1, 4), help="Priority (1=urgent, 4=low)")
@click.option("--label", "labels", multiple=True, help="Label name (repeatable)")
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

    try:
        team_id = resolve_team_id(client, team_key)
        state_id = resolve_status(client, team_key, status) if status else None
        assignee_id = resolve_assignee(client, team_key, assignee) if assignee else None
        label_ids = resolve_labels(client, team_key, list(labels)) if labels else None
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    _output(
        create_issue(
            client,
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
@click.option("--status", help="Status name")
@click.option("--assignee", help="Assignee name")
@click.option("--priority", type=click.IntRange(1, 4), help="Priority (1=urgent, 4=low)")
@click.option("--label", "labels", multiple=True, help="Label name (repeatable, replaces all)")
def update_issue_cmd(
    identifier: str,
    title: str | None,
    status: str | None,
    assignee: str | None,
    priority: int | None,
    labels: tuple[str, ...],
) -> None:
    """Update an issue."""
    client = _get_client()

    # Need team context for name resolution
    team_key: str | None = None
    if status or assignee or labels:
        detail = get_issue(client, identifier)
        team_key = detail.get("team")
        if not team_key:
            print("Error: could not determine team for issue", file=sys.stderr)
            sys.exit(1)

    try:
        state_id = resolve_status(client, team_key, status) if status and team_key else None
        assignee_id = (
            resolve_assignee(client, team_key, assignee) if assignee and team_key else None
        )
        label_ids = resolve_labels(client, team_key, list(labels)) if labels and team_key else None
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    _output(
        update_issue(
            client,
            identifier,
            title=title,
            state_id=state_id,
            assignee_id=assignee_id,
            priority=priority,
            label_ids=label_ids,
        )
    )


@linear.command()
@click.argument("identifier")
def comments(identifier: str) -> None:
    """List comments on an issue."""
    _output(get_comments(_get_client(), identifier))


@linear.command("comment")
@click.argument("identifier")
@click.option("--message", "-m", help="Comment body")
def comment_cmd(identifier: str, message: str | None) -> None:
    """Add a comment to an issue."""
    if not message:
        if sys.stdin.isatty():
            print("Error: provide --message or pipe content via stdin", file=sys.stderr)
            sys.exit(1)
        message = sys.stdin.read().strip()

    if not message:
        print("Error: empty comment message", file=sys.stderr)
        sys.exit(1)

    _output(create_comment(_get_client(), identifier, body=message))


@linear.command()
@click.argument("file_path", type=click.Path(exists=True))
def upload(file_path: str) -> None:
    """Upload a file to Linear's storage."""
    try:
        _output(upload_file(_get_client(), file_path))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
