"""CLI interface for kv tool."""

import sys

import click
from rich.console import Console
from rich.table import Table

from kv.db import (
    clean_expired,
    delete_key,
    get_db_path,
    get_value,
    init_db,
    list_keys,
    set_expiry,
    set_value,
    validate_key,
)

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
    if not validate_key(key):
        console.print("[red]Error:[/red] Key must be lower-kebab-case and <= 100 characters")
        sys.exit(1)

    if value is None:
        value = sys.stdin.read().rstrip("\n")

    db_path = get_db_path()
    conn = init_db(db_path)
    set_value(conn, key, value)
    conn.close()


@main.command("get")
@click.argument("key")
def get_cmd(key: str) -> None:
    """Get value for a key."""
    db_path = get_db_path()
    conn = init_db(db_path)
    value, is_expired = get_value(conn, key)
    conn.close()

    if value is None:
        sys.exit(2)

    if is_expired:
        sys.exit(3)

    print(value)


@main.command("list")
@click.option("--plain", is_flag=True, help="Output in plain format")
def list_cmd(plain: bool) -> None:
    """List all keys."""
    from datetime import datetime

    db_path = get_db_path()
    conn = init_db(db_path)
    keys = list_keys(conn)
    conn.close()

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
    db_path = get_db_path()
    conn = init_db(db_path)
    exists = set_expiry(conn, key, ttl)
    conn.close()

    if not exists:
        console.print(f"[red]Error:[/red] Key '{key}' not found")
        sys.exit(2)


@main.command("rm")
@click.argument("key")
def rm_cmd(key: str) -> None:
    """Remove a key."""
    db_path = get_db_path()
    conn = init_db(db_path)
    exists = delete_key(conn, key)
    conn.close()

    if not exists:
        console.print(f"[red]Error:[/red] Key '{key}' not found")
        sys.exit(2)


@main.command("clean")
def clean_cmd() -> None:
    """Remove all expired entries."""
    db_path = get_db_path()
    conn = init_db(db_path)
    count = clean_expired(conn)
    conn.close()

    console.print(f"[green]Removed {count} expired entries[/green]")


if __name__ == "__main__":
    main()
