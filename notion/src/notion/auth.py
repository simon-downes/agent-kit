"""Authentication and credential management."""

import json
import subprocess
import sys

from rich.console import Console

console = Console()

NOTION_MCP_URL = "https://mcp.notion.com/mcp"


def get_credentials() -> dict[str, str]:
    """Get Notion OAuth credentials.

    Returns dict with access_token and other token data.
    Exits with code 2 on auth errors.
    """
    try:
        result = subprocess.run(
            ["oauth", "show", "notion"], capture_output=True, text=True, check=False
        )

        if result.returncode == 2:
            console.print("[red]Error:[/red] Not authenticated with Notion")
            console.print("\nRun: [cyan]uvx oauth login notion[/cyan]")
            sys.exit(2)

        if result.returncode != 0:
            console.print("[red]Error:[/red] Failed to fetch credentials")
            console.print("\nRun: [cyan]uvx oauth login notion[/cyan]")
            sys.exit(2)

        return json.loads(result.stdout)  # type: ignore[no-any-return]

    except FileNotFoundError:
        console.print("[red]Error:[/red] oauth tool not found")
        console.print("\nInstall it with: [cyan]uv tool install ./oauth[/cyan]")
        sys.exit(2)
    except json.JSONDecodeError:
        console.print("[red]Error:[/red] Invalid credential format")
        console.print("\nTry re-authenticating: [cyan]uvx oauth login notion[/cyan]")
        sys.exit(2)
