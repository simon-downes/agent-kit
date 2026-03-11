"""CLI interface for check tool."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table

console = Console()


def get_config_path() -> Path:
    """Get config file path."""
    return Path.home() / ".agent-kit" / "tools.yaml"


def load_config() -> dict:
    """Load tools configuration."""
    config_path = get_config_path()
    if not config_path.exists():
        return {"tools": {}}

    with open(config_path) as f:
        return yaml.safe_load(f)


def check_tool(name: str, config: dict, verbose: bool = False) -> dict:
    """Check if tool is installed and authenticated.

    Returns:
        dict with keys: found, version, authenticated, auth_output, auth_exit_code
    """
    result = {
        "found": False,
        "version": None,
        "authenticated": None,
        "auth_output": None,
        "auth_exit_code": None,
    }

    # Check if command exists
    version_cmd = config.get("version_cmd", "").split()[0]
    if not shutil.which(version_cmd):
        return result

    result["found"] = True

    # Get version
    try:
        output = subprocess.check_output(
            config["version_cmd"],
            shell=True,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if "version_pattern" in config:
            match = re.search(config["version_pattern"], output)
            if match:
                result["version"] = match.group(1)
    except subprocess.CalledProcessError:
        pass

    # Check authentication
    if "auth_cmd" in config:
        try:
            output = subprocess.check_output(
                config["auth_cmd"],
                shell=True,
                stderr=subprocess.STDOUT,
                text=True,
            )
            result["authenticated"] = True
            result["auth_output"] = output.strip()
            result["auth_exit_code"] = 0
        except subprocess.CalledProcessError as e:
            result["authenticated"] = False
            result["auth_output"] = e.output.strip() if e.output else ""
            result["auth_exit_code"] = e.returncode

    return result


@click.command()
@click.argument("tools", nargs=-1)
@click.option("-v", "--verbose", is_flag=True, help="Show detailed auth output")
def main(tools: tuple[str, ...], verbose: bool) -> None:
    """Check - Verify development tools are installed and authenticated."""
    config = load_config()
    tool_configs = config.get("tools", {})

    if not tool_configs:
        console.print("[yellow]No tools configured in ~/.agent-kit/tools.yaml[/yellow]")
        sys.exit(0)

    # Determine which tools to check
    if tools:
        # Check only specified tools, in config order
        tools_to_check = []
        for name in tool_configs.keys():
            if name in tools:
                tools_to_check.append(name)

        # Check for unknown tools
        unknown = set(tools) - set(tool_configs.keys())
        if unknown:
            for name in unknown:
                console.print(f"[red]✗ {name:12} unknown tool[/red]")
    else:
        # Check all tools in config order
        tools_to_check = list(tool_configs.keys())

    if not tools_to_check:
        sys.exit(0)

    # Check tools
    results = {}
    for name in tools_to_check:
        results[name] = check_tool(name, tool_configs[name], verbose)

    # Determine exit code
    has_missing = any(not r["found"] for r in results.values())
    has_auth_failure = any(
        r["authenticated"] is False for r in results.values()
    )

    exit_code = 0
    if has_missing:
        exit_code = 2
    elif has_auth_failure:
        exit_code = 1

    # Display results
    if verbose:
        # Verbose output
        for name in tools_to_check:
            result = results[name]
            config_item = tool_configs[name]

            console.print(f"\n[bold]{name}[/bold]")

            if not result["found"]:
                console.print("  [bright_red]✗ Not found[/bright_red]")
                continue

            if result["version"]:
                console.print(
                    f"  [green]✓ Version[/green]: [bright_magenta]{result['version']}[/bright_magenta]"
                )

            if "auth_cmd" in config_item:
                exit_code_color = "green" if result["auth_exit_code"] == 0 else "bright_red"
                if result["authenticated"]:
                    console.print("  [green]✓ Authenticated[/green]")
                    console.print(f"    Exit code: [{exit_code_color}]{result['auth_exit_code']}[/{exit_code_color}]")
                    if result["auth_output"]:
                        console.print(f"    Output: {result['auth_output']}")
                else:
                    console.print("  [yellow]✗ Not authenticated[/yellow]")
                    console.print(f"    Exit code: [{exit_code_color}]{result['auth_exit_code']}[/{exit_code_color}]")
                    if result["auth_output"]:
                        console.print(f"    Output: {result['auth_output']}")
    else:
        # Table output
        table = Table(show_header=True)
        table.add_column("Tool", style="cyan")
        table.add_column("Version")
        table.add_column("Auth")

        for name in tools_to_check:
            result = results[name]

            if not result["found"]:
                table.add_row(
                    f"[bright_red]✗ {name}[/bright_red]",
                    "[bright_red]-[/bright_red]",
                    "",
                )
                continue

            version_str = result["version"] or "[dim]unknown[/dim]"

            if result["authenticated"] is None:
                auth_str = ""
                tool_name = f"[green]✓ {name}[/green]"
            elif result["authenticated"]:
                auth_str = "[green]✓[/green]"
                tool_name = f"[green]✓ {name}[/green]"
            else:
                auth_str = "[yellow]✗[/yellow]"
                tool_name = f"[green]✓[/green] [yellow]{name}[/yellow]"

            table.add_row(
                tool_name,
                version_str,
                auth_str,
            )

        console.print(table)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
