"""Brain CLI subcommands."""

import click

from agent_kit.brain.client import BrainClient, resolve_brain_dir
from agent_kit.config import load_config
from agent_kit.errors import handle_errors, output


def _get_client() -> BrainClient:
    """Create a BrainClient from config."""
    config = load_config()
    return BrainClient(resolve_brain_dir(config))


@click.group()
def brain() -> None:
    """Brain — query and manage the second brain."""


@brain.command()
@click.option("--type", "entity_type", help="Filter by entity type")
@click.option("--slug", help="Lookup a specific entity by slug")
@handle_errors
def index(entity_type: str | None, slug: str | None) -> None:
    """Query the brain index."""
    client = _get_client()
    idx = client.load_index()
    output(client.query_index(idx, entity_type=entity_type, slug=slug))


@brain.command()
@click.argument("terms", nargs=-1, required=True)
@click.option("--limit", default=10, help="Maximum results")
@handle_errors
def search(terms: tuple[str, ...], limit: int) -> None:
    """Search the brain with one or more terms."""
    client = _get_client()
    results = client.search(list(terms), limit=limit)
    output(results)


@brain.command()
@handle_errors
def reindex() -> None:
    """Rebuild index.yaml from filesystem contents."""
    client = _get_client()
    idx = client.reindex()
    output(idx)


@brain.command()
@click.argument("message")
@click.option("--paths", multiple=True, help="Specific files to stage (repeatable).")
@handle_errors
def commit(message: str, paths: tuple[str, ...]) -> None:
    """Stage and commit changes."""
    client = _get_client()
    sha = client.commit(message, list(paths) if paths else None)
    if sha:
        print(sha)
    else:
        print("nothing to commit")


@brain.command()
@click.argument("path")
@handle_errors
def ref(path: str) -> None:
    """Record a brain entry access for reference tracking."""
    client = _get_client()
    client.record_ref(path)


@brain.command()
@click.option("--top", "top_n", type=int, help="Show most-referenced entries")
@click.option("--stale", is_flag=True, help="Show unreferenced entries")
@click.option("--since", "since_days", type=int, default=90, help="Days threshold for --stale")
@handle_errors
def refs(top_n: int | None, stale: bool, since_days: int) -> None:
    """Query reference tracking data."""
    client = _get_client()
    if stale:
        output(client.stale_refs(since_days))
    elif top_n:
        output(client.top_refs(top_n))
    else:
        output(client.top_refs(10))


@brain.command()
@click.argument("name", required=False)
@handle_errors
def project(name: str | None) -> None:
    """Get project config from the brain."""
    if not name:
        from agent_kit.project import resolve_project

        info = resolve_project(load_config())
        name = info["name"]

    client = _get_client()
    result = client.find_project(name)
    if not result:
        raise ValueError(f"project '{name}' not found in brain")
    output(result)


@brain.command()
@handle_errors
def status() -> None:
    """Show brain status."""
    client = _get_client()
    output(client.brain_status())
