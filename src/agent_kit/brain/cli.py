"""Brain CLI subcommands."""

from pathlib import Path

import click

from agent_kit.brain.client import BrainClient, resolve_brain_dir, validate_name
from agent_kit.config import load_config
from agent_kit.errors import handle_errors, output


def _get_client() -> BrainClient:
    """Create a BrainClient from config."""
    config = load_config()
    return BrainClient(resolve_brain_dir(config))


def _resolve_context(client: BrainClient, name: str) -> Path:
    """Validate and resolve a context name to a path."""
    validate_name(name)
    context_path = client._brain_dir / name
    if not context_path.exists():
        raise ValueError(f"context '{name}' not found")
    return context_path


@click.group()
def brain() -> None:
    """Brain — query and manage the second brain."""


@brain.command()
@click.argument("context", required=False)
@handle_errors
def init(context: str | None) -> None:
    """Initialise the brain or a specific context."""
    config = load_config()
    client = _get_client()

    if context:
        validate_name(context)
        client._brain_dir.mkdir(parents=True, exist_ok=True)
        contexts = client.configured_contexts(config)
        repo = contexts.get(context)
        result = client.init_context(context, repo)
        if result:
            print(result)
        else:
            print(f"{context} already exists")
    else:
        actions = client.init_brain(config)
        if actions:
            for action in actions:
                print(action)
        else:
            print("brain already initialised")


@brain.command()
@click.argument("context", required=False)
@click.option("--type", "entity_type", help="Filter by entity type")
@click.option("--slug", help="Lookup a specific entity by slug")
@handle_errors
def index(context: str | None, entity_type: str | None, slug: str | None) -> None:
    """Query the brain index."""
    client = _get_client()

    if not context:
        output(client.list_contexts())
        return

    context_path = _resolve_context(client, context)
    idx = client.load_index(context_path)
    output(client.query_index(idx, entity_type=entity_type, slug=slug))


@brain.command()
@click.argument("query")
@click.option("--context", help="Limit search to a specific context")
@click.option("--limit", default=20, help="Maximum results")
@handle_errors
def search(query: str, context: str | None, limit: int) -> None:
    """Search the brain for matching entities, content, and memory."""
    client = _get_client()
    results = client.search(query, context=context, limit=limit)
    for r in results:
        r.pop("modified", None)
    output(results)


@brain.command()
@click.argument("context")
@handle_errors
def reindex(context: str) -> None:
    """Rebuild index.yaml for a context from filesystem contents."""
    client = _get_client()
    context_path = _resolve_context(client, context)
    idx = client.reindex_context(context_path)
    output(idx)


@brain.command()
@click.argument("context")
@click.option("-m", "--message", required=True, help="Commit message")
@click.option("--paths", multiple=True, help="Specific files to stage (repeatable).")
@handle_errors
def commit(context: str, message: str, paths: tuple[str, ...]) -> None:
    """Stage and commit changes in a context."""
    client = _get_client()
    context_path = _resolve_context(client, context)
    sha = client.commit_context(context_path, message, list(paths) if paths else None)
    if sha:
        print(f"{context}: {sha}")
    else:
        print(f"{context}: nothing to commit")


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
@click.argument("context", required=False)
@handle_errors
def status(context: str | None) -> None:
    """Show brain status."""
    client = _get_client()

    if context:
        output(client.context_status(_resolve_context(client, context)))
    else:
        output(client.brain_status())


@brain.command()
@click.argument("context", required=False)
@handle_errors
def validate(context: str | None) -> None:
    """Validate brain structure and index integrity."""
    config = load_config()
    client = _get_client()

    findings: list[dict] = []

    if context:
        findings = client.validate_context(_resolve_context(client, context))
    else:
        for c in client.list_contexts():
            findings.extend(client.validate_context(client._brain_dir / c))
        findings.extend(client.validate_origins(config))

    output(findings)
    if any(f["level"] == "error" for f in findings):
        raise SystemExit(1)
