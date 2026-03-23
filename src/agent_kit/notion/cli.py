"""CLI interface for notion tool."""

import asyncio
import sys

import click
from rich.console import Console

from agent_kit.notion.auth import get_credentials
from agent_kit.notion.mcp import connect_to_notion
from agent_kit.notion.output import format_json, format_markdown_raw, format_markdown_terminal

console = Console()


@click.group()
def main() -> None:
    """Notion - Search and fetch Notion pages."""
    pass


@main.command()
@click.argument("query")
@click.option("--json", "output_json", is_flag=True, help="Output raw JSON")
@click.option("--raw", is_flag=True, help="Output raw markdown")
def search(query: str, output_json: bool, raw: bool) -> None:
    """Search Notion workspace."""
    asyncio.run(_search(query, output_json, raw))


async def _search(query: str, output_json: bool, raw: bool) -> None:
    """Async implementation of search."""
    credentials = get_credentials()
    access_token = credentials.get("access_token")

    if not access_token:
        console.print("[red]Error:[/red] No access token found")
        sys.exit(2)

    session_context = None
    streams_context = None

    try:
        session, session_context, streams_context = await connect_to_notion(access_token)

        result = await session.call_tool("notion-search", {"query": query})
        content = [c.model_dump() for c in result.content]

        if output_json:
            print(format_json(content))
        elif raw:
            print(format_markdown_raw(content))
        else:
            format_markdown_terminal(content, console)

    except Exception as e:
        error_msg = str(e)
        # Check for auth errors
        if "401" in error_msg or "Unauthorized" in error_msg:
            console.print("[red]Error:[/red] Authentication failed")
            console.print("\nYour credentials may have expired. Try re-authenticating:")
            console.print("[cyan]ak oauth login notion[/cyan]")
            sys.exit(2)

        console.print(f"[red]Error:[/red] {e}")
        sys.exit(3)
    finally:
        if session_context:
            try:
                await session_context.__aexit__(None, None, None)
            except Exception:
                pass
        if streams_context:
            try:
                await streams_context.__aexit__(None, None, None)
            except Exception:
                pass


@main.command()
@click.argument("page_id_or_url")
@click.option("--json", "output_json", is_flag=True, help="Output raw JSON")
@click.option("--raw", is_flag=True, help="Output raw markdown")
def fetch(page_id_or_url: str, output_json: bool, raw: bool) -> None:
    """Fetch a Notion page by ID or URL."""
    asyncio.run(_fetch(page_id_or_url, output_json, raw))


async def _fetch(page_id_or_url: str, output_json: bool, raw: bool) -> None:
    """Async implementation of fetch."""
    credentials = get_credentials()
    access_token = credentials.get("access_token")

    if not access_token:
        console.print("[red]Error:[/red] No access token found")
        sys.exit(2)

    session_context = None
    streams_context = None

    try:
        session, session_context, streams_context = await connect_to_notion(access_token)

        result = await session.call_tool("notion-fetch", {"id": page_id_or_url})
        content = [c.model_dump() for c in result.content]

        if output_json:
            print(format_json(content))
        elif raw:
            print(format_markdown_raw(content))
        else:
            format_markdown_terminal(content, console)

    except Exception as e:
        error_msg = str(e)
        # Check for auth errors
        if "401" in error_msg or "Unauthorized" in error_msg:
            console.print("[red]Error:[/red] Authentication failed")
            console.print("\nYour credentials may have expired. Try re-authenticating:")
            console.print("[cyan]ak oauth login notion[/cyan]")
            sys.exit(2)

        console.print(f"[red]Error:[/red] {e}")
        sys.exit(3)
    finally:
        if session_context:
            try:
                await session_context.__aexit__(None, None, None)
            except Exception:
                pass
        if streams_context:
            try:
                await streams_context.__aexit__(None, None, None)
            except Exception:
                pass


if __name__ == "__main__":
    main()
