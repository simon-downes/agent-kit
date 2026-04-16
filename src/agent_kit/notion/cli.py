"""Notion CLI subcommands."""

import asyncio
import json
import os
import sys
from typing import Any

import click

from agent_kit.config import load_config
from agent_kit.mcp import mcp_session
from agent_kit.notion.client import (
    NOTION_MCP_URL,
    ConfigError,
    ScopeError,
    check_read_scope,
    check_write_scope,
    create_comment,
    create_page,
    extract_id,
    fetch_comments,
    fetch_database,
    fetch_page,
    list_view_names,
    query_database,
    require_read,
    require_write,
    search,
    update_page,
)
from agent_kit.notion.filters import parse_filter


def _get_token() -> str:
    """Get Notion token from credential store or environment."""
    from agent_kit.auth import get_field

    token = get_field("notion", "access_token") or os.environ.get("NOTION_TOKEN")
    if not token:
        print(
            "Error: no Notion credentials — run 'ak auth set notion access_token'",
            file=sys.stderr,
        )
        sys.exit(2)
    return token


def _output(data: Any) -> None:
    """Write JSON to stdout."""
    print(json.dumps(data, indent=2))


def _run(coro: Any) -> Any:
    """Bridge sync Click command to async MCP call."""
    try:
        return asyncio.run(coro)
    except Exception as e:
        # Unwrap nested ExceptionGroups (from anyio/MCP task groups)
        cause = e
        while isinstance(cause, ExceptionGroup) and cause.exceptions:
            cause = cause.exceptions[0]

        if isinstance(cause, (ScopeError, ConfigError)):
            print(f"Error: {cause}", file=sys.stderr)
            sys.exit(1)

        msg = str(cause)
        if "401" in msg or "Unauthorized" in msg:
            print(
                "Error: Notion authentication failed (token may be expired)",
                file=sys.stderr,
            )
            sys.exit(2)
        if "429" in msg or "rate limit" in msg.lower():
            print("Error: Notion rate limit exceeded, try again later", file=sys.stderr)
            sys.exit(1)
        print(f"Error: {cause}", file=sys.stderr)
        sys.exit(1)


def _parse_props(props: tuple[str, ...]) -> dict[str, str]:
    """Parse --prop Key=Value tuples into a dict."""
    result = {}
    for p in props:
        if "=" not in p:
            print(
                f"Error: invalid property format: {p!r} (expected Key=Value)",
                file=sys.stderr,
            )
            sys.exit(1)
        key, value = p.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def _session(token: str):
    """Create an MCP session context manager."""
    return mcp_session(NOTION_MCP_URL, {"Authorization": f"Bearer {token}"})


@click.group()
def notion() -> None:
    """Notion — search, fetch, and manage Notion content."""


# --- Read commands ---


@notion.command("search")
@click.argument("query")
@click.option("--limit", default=10, help="Maximum results to return")
@click.option(
    "--type",
    "filter_type",
    type=click.Choice(["page", "database"]),
    help="Filter by type",
)
def search_cmd(query: str, limit: int, filter_type: str | None) -> None:
    """Search the Notion workspace."""
    config = load_config()
    require_read(config)
    token = _get_token()

    async def _search() -> list:
        async with _session(token) as session:
            return await search(session, query, limit=limit, filter_type=filter_type)

    _output(_run(_search()))


@notion.command()
@click.argument("id_or_url")
@click.option("--markdown", is_flag=True, help="Output as markdown instead of JSON")
@click.option("--properties", is_flag=True, help="Include page properties")
def page(id_or_url: str, markdown: bool, properties: bool) -> None:
    """Fetch a Notion page by ID or URL."""
    config = load_config()
    require_read(config)
    page_id = extract_id(id_or_url)
    token = _get_token()

    async def _fetch() -> dict:
        async with _session(token) as session:
            text, result = await fetch_page(session, page_id, properties=properties)
            check_read_scope(config, page_id, text)
            return result

    result = _run(_fetch())

    if markdown:
        text = result.get("content", result.get("text", ""))
        if isinstance(text, dict):
            text = json.dumps(text, indent=2)
        print(text)
    else:
        _output(result)


@notion.command()
@click.argument("id_or_url")
@click.option("--views", is_flag=True, help="List available views")
def db(id_or_url: str, views: bool) -> None:
    """Fetch a Notion database schema."""
    config = load_config()
    require_read(config)
    db_id = extract_id(id_or_url)
    token = _get_token()

    async def _fetch() -> dict | list:
        async with _session(token) as session:
            text, result = await fetch_database(session, db_id)
            check_read_scope(config, db_id, text)
            if views:
                return list_view_names(text)
            return result

    _output(_run(_fetch()))


@notion.command()
@click.argument("id_or_url")
@click.option("--view", "view_name", help="View name to query (default: first view)")
@click.option("--filter", "filters", multiple=True, help="Filter as Key=Value (repeatable)")
@click.option("--sort", "sort_expr", help="Sort as property:asc or property:desc")
@click.option("--columns", help="Comma-separated list of properties to include")
@click.option("--limit", default=None, type=int, help="Maximum results to return")
def query(
    id_or_url: str,
    view_name: str | None,
    filters: tuple[str, ...],
    sort_expr: str | None,
    columns: str | None,
    limit: int | None,
) -> None:
    """Query a Notion database."""
    config = load_config()
    require_read(config)
    db_id = extract_id(id_or_url)
    token = _get_token()

    # Parse filters into (key, op, value) tuples
    parsed_filters = None
    if filters:
        parsed_filters = []
        for f in filters:
            key, op, value = parse_filter(f)
            parsed_filters.append((key, op, value))

    # Parse sort
    sort_key = None
    sort_reverse = False
    if sort_expr:
        parts = sort_expr.split(":", 1)
        sort_key = parts[0]
        if len(parts) > 1 and parts[1] in ("desc", "descending"):
            sort_reverse = True

    col_list = [c.strip() for c in columns.split(",")] if columns else None

    async def _query() -> list:
        async with _session(token) as session:
            rows, text = await query_database(
                session,
                db_id,
                view_name=view_name,
                filters=parsed_filters,
                sort_key=sort_key,
                sort_reverse=sort_reverse,
                columns=col_list,
                limit=limit,
            )
            check_read_scope(config, db_id, text)
            return rows

    _output(_run(_query()))


@notion.command()
@click.argument("id_or_url")
@click.option("--limit", default=None, type=int, help="Maximum results to return")
def comments(id_or_url: str, limit: int | None) -> None:
    """Fetch comments on a Notion page."""
    config = load_config()
    require_read(config)
    page_id = extract_id(id_or_url)
    token = _get_token()

    async def _fetch() -> list:
        async with _session(token) as session:
            # Scope check: fetch page first to get ancestors
            text, _ = await fetch_page(session, page_id)
            check_read_scope(config, page_id, text)
            return await fetch_comments(session, page_id, limit=limit)

    _output(_run(_fetch()))


# --- Write commands ---


@notion.command("create-page")
@click.argument("parent_id")
@click.option("--title", help="Page title")
@click.option("--prop", "props", multiple=True, help="Property as Key=Value (repeatable)")
def create_page_cmd(parent_id: str, title: str | None, props: tuple[str, ...]) -> None:
    """Create a new Notion page."""
    config = load_config()
    require_write(config)
    token = _get_token()
    properties = _parse_props(props) if props else None

    body = None
    if not sys.stdin.isatty():
        body = sys.stdin.read().strip() or None

    async def _create() -> dict:
        async with _session(token) as session:
            # Scope check: fetch parent to get ancestors
            text, _ = await fetch_page(session, parent_id)
            check_write_scope(config, parent_id, text)
            return await create_page(
                session, parent_id, title=title, properties=properties, content=body
            )

    _output(_run(_create()))


@notion.command("update-page")
@click.argument("id_or_url")
@click.option("--prop", "props", multiple=True, help="Property as Key=Value (repeatable)")
def update_page_cmd(id_or_url: str, props: tuple[str, ...]) -> None:
    """Update a Notion page's properties."""
    config = load_config()
    require_write(config)
    page_id = extract_id(id_or_url)
    token = _get_token()
    properties = _parse_props(props) if props else None

    async def _update() -> dict:
        async with _session(token) as session:
            text, _ = await fetch_page(session, page_id)
            check_write_scope(config, page_id, text)
            return await update_page(session, page_id, properties=properties)

    _output(_run(_update()))


@notion.command("comment")
@click.argument("id_or_url")
@click.option("--message", "-m", help="Comment message")
def comment_cmd(id_or_url: str, message: str | None) -> None:
    """Add a comment to a Notion page."""
    config = load_config()
    require_write(config)
    page_id = extract_id(id_or_url)
    token = _get_token()

    if not message:
        if sys.stdin.isatty():
            print("Error: provide --message or pipe content via stdin", file=sys.stderr)
            sys.exit(1)
        message = sys.stdin.read().strip()

    if not message:
        print("Error: empty comment message", file=sys.stderr)
        sys.exit(1)

    async def _comment() -> dict:
        async with _session(token) as session:
            text, _ = await fetch_page(session, page_id)
            check_write_scope(config, page_id, text)
            return await create_comment(session, page_id, message=message)

    _output(_run(_comment()))
