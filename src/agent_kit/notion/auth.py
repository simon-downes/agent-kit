"""Authentication and credential management."""

import sys

from rich.console import Console

from agent_kit.oauth.tokens import get_token

console = Console()

NOTION_MCP_URL = "https://mcp.notion.com/mcp"


def get_credentials() -> dict[str, str]:
    """Get Notion OAuth credentials.

    Returns dict with access_token and other token data.
    Exits with code 2 on auth errors.
    """
    token_data = get_token("notion")

    if not token_data:
        console.print("[red]Error:[/red] Not authenticated with Notion")
        console.print("\nRun: [cyan]ak oauth login notion[/cyan]")
        sys.exit(2)

    return token_data
