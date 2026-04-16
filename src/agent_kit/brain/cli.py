"""Brain CLI subcommands."""

from pathlib import Path

import click

from agent_kit.brain.client import (
    context_status,
    create_context,
    list_contexts,
    load_index,
    query_index,
    resolve_brain_dir,
    validate_context,
    validate_name,
)
from agent_kit.config import load_config
from agent_kit.errors import handle_errors, output


def _resolve_context(brain_dir: Path, name: str) -> Path:
    """Validate and resolve a context name to a path."""
    validate_name(name)
    context_path = brain_dir / name
    if not context_path.exists():
        raise ValueError(f"context '{name}' not found")
    return context_path


@click.group()
def brain() -> None:
    """Brain — query and manage the second brain."""


@brain.command()
@click.argument("context", required=False)
@click.option("--type", "entity_type", help="Filter by entity type")
@click.option("--slug", help="Lookup a specific entity by slug")
@handle_errors
def index(context: str | None, entity_type: str | None, slug: str | None) -> None:
    """Query the brain index.

    Without arguments, lists all contexts. With a context name, shows its index.
    """
    config = load_config()
    brain_dir = resolve_brain_dir(config)

    if not context:
        output(list_contexts(brain_dir))
        return

    context_path = _resolve_context(brain_dir, context)
    idx = load_index(context_path)
    output(query_index(idx, entity_type=entity_type, slug=slug))


@brain.command("create-context")
@click.argument("name")
@handle_errors
def create_context_cmd(name: str) -> None:
    """Create a brain context with standard directory structure."""
    config = load_config()
    brain_dir = resolve_brain_dir(config)
    brain_dir.mkdir(parents=True, exist_ok=True)
    create_context(brain_dir, name)
    print("OK")


@brain.command()
@click.argument("context", required=False)
@handle_errors
def status(context: str | None) -> None:
    """Show brain status: git changes and unprocessed raw items.

    Without arguments, shows status for all contexts.
    """
    config = load_config()
    brain_dir = resolve_brain_dir(config)

    if context:
        output(context_status(_resolve_context(brain_dir, context)))
    else:
        output([context_status(brain_dir / c) for c in list_contexts(brain_dir)])


@brain.command()
@click.argument("context", required=False)
@handle_errors
def validate(context: str | None) -> None:
    """Validate brain structure and index integrity.

    Without arguments, validates all contexts.
    """
    config = load_config()
    brain_dir = resolve_brain_dir(config)

    if context:
        findings = validate_context(_resolve_context(brain_dir, context))
    else:
        findings = []
        for c in list_contexts(brain_dir):
            findings.extend(validate_context(brain_dir / c))

    output(findings)
    if any(f["level"] == "error" for f in findings):
        raise SystemExit(1)
