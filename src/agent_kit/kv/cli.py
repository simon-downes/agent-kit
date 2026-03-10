"""CLI interface for kv tool."""

import sys

import click
from rich.console import Console
from rich.table import Table

from agent_kit.kv import db

console = Console()


@click.group()
def main() -> None:
    """KV - A simple key-value store."""
    pass


@main.command("set")
@click.argument("key")
@click.argument("value", required=False)
def set_cmd(key: str, value: str | None) -> None:
    """Set a key-value pair."""
    if value is None:
        value = sys.stdin.read().rstrip("\n")

    try:
        db.set(key, value)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command("get")
@click.argument("key")
def get_cmd(key: str) -> None:
    """Get value for a key."""
    value = db.get(key)
    if value is None:
        sys.exit(2)
    print(value)


@main.command("list")
@click.option("--plain", is_flag=True, help="Output in plain format")
def list_cmd(plain: bool) -> None:
    """List all keys."""
    from datetime import datetime

    keys = db.list_all()

    if plain:
        for key, expires_at in keys:
            expiry_str = expires_at if expires_at else "never"
            print(f"{key}\t{expiry_str}")
    else:
        table = Table(show_header=True)
        table.add_column("Key")
        table.add_column("Expires")

        now = datetime.now()
        for key, expires_at in keys:
            if expires_at:
                expiry = datetime.fromisoformat(expires_at)
                expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S")
                if expiry < now:
                    table.add_row(f"[dim]{key}[/dim]", f"[red]{expiry_str} (expired)[/red]")
                else:
                    table.add_row(key, expiry_str)
            else:
                table.add_row(key, "[dim]never[/dim]")

        console.print(table)


@main.command("expire")
@click.argument("key")
@click.argument("ttl", type=int)
def expire_cmd(key: str, ttl: int) -> None:
    """Set expiry for a key (TTL in seconds)."""
    exists = db.expire(key, ttl)
    if not exists:
        console.print(f"[red]Error:[/red] Key '{key}' not found")
        sys.exit(2)


@main.command("rm")
@click.argument("key")
def rm_cmd(key: str) -> None:
    """Remove a key."""
    exists = db.delete(key)
    if not exists:
        console.print(f"[red]Error:[/red] Key '{key}' not found")
        sys.exit(2)


@main.command("clean")
def clean_cmd() -> None:
    """Remove all expired entries."""
    count = db.clean_expired_keys()
    console.print(f"[green]Removed {count} expired entries[/green]")


if __name__ == "__main__":
    main()
