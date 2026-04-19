"""Brain CLI subcommands."""

from pathlib import Path

import click

from agent_kit.brain.client import (
    brain_status,
    commit_context,
    find_project,
    init_brain,
    init_context,
    list_contexts,
    load_index,
    query_index,
    reindex_context,
    resolve_brain_dir,
    search_brain,
    validate_context,
    validate_name,
    validate_origins,
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
@handle_errors
def init(context: str | None) -> None:
    """Initialise the brain or a specific context.

    Without arguments: creates _raw pipeline dirs and initialises/clones all
    configured contexts. With a context name: initialises just that context
    (clones from config if a repo is specified, otherwise creates locally).
    """
    config = load_config()
    brain_dir = resolve_brain_dir(config)

    if context:
        validate_name(context)
        brain_dir.mkdir(parents=True, exist_ok=True)
        from agent_kit.brain.client import configured_contexts

        contexts = configured_contexts(config)
        repo = contexts.get(context)
        result = init_context(brain_dir, context, repo)
        if result:
            print(result)
        else:
            print(f"{context} already exists")
    else:
        actions = init_brain(brain_dir, config)
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


@brain.command()
@click.argument("query")
@click.option("--context", help="Limit search to a specific context")
@click.option("--limit", default=20, help="Maximum results")
@handle_errors
def search(query: str, context: str | None, limit: int) -> None:
    """Search the brain for matching entities, content, and memory.

    Searches index metadata (name, tags, summary), file content, and
    conversation memory. Results are ranked by match quality and recency.
    """
    config = load_config()
    brain_dir = resolve_brain_dir(config)
    results = search_brain(brain_dir, query, context=context, limit=limit)
    # Strip internal mtime from output
    for r in results:
        r.pop("modified", None)
    output(results)


@brain.command()
@click.argument("context")
@handle_errors
def reindex(context: str) -> None:
    """Rebuild index.yaml for a context from filesystem contents.

    Scans entity directories, extracts metadata from frontmatter, and merges
    with existing index entries (preserving curated summaries).
    """
    config = load_config()
    brain_dir = resolve_brain_dir(config)
    context_path = _resolve_context(brain_dir, context)
    idx = reindex_context(context_path)
    output(idx)


@brain.command()
@click.argument("context")
@click.option("-m", "--message", required=True, help="Commit message")
@click.option("--paths", multiple=True, help="Specific files to stage (repeatable).")
@handle_errors
def commit(context: str, message: str, paths: tuple[str, ...]) -> None:
    """Stage and commit changes in a context.

    By default stages all changes. Use --paths to stage specific files only,
    preventing one agent's commit from sweeping up another agent's work.
    """
    config = load_config()
    brain_dir = resolve_brain_dir(config)
    context_path = _resolve_context(brain_dir, context)
    sha = commit_context(context_path, message, list(paths) if paths else None)
    if sha:
        print(f"{context}: {sha}")
    else:
        print(f"{context}: nothing to commit")


@brain.command()
@click.argument("name", required=False)
@handle_errors
def project(name: str | None) -> None:
    """Get project config from the brain.

    Resolves by project directory name. Without arguments, infers from
    current working directory. Searches across all contexts.
    """
    if not name:
        from agent_kit.project import resolve_project_name

        name, _ = resolve_project_name(load_config())

    config = load_config()
    brain_dir = resolve_brain_dir(config)
    result = find_project(brain_dir, name)
    if not result:
        raise ValueError(f"project '{name}' not found in brain")
    output(result)


@brain.command()
@click.argument("context", required=False)
@handle_errors
def status(context: str | None) -> None:
    """Show brain status.

    Without arguments, shows overall status including _raw pipeline and all contexts.
    With a context name, shows just that context.
    """
    config = load_config()
    brain_dir = resolve_brain_dir(config)

    if context:
        from agent_kit.brain.client import context_status

        output(context_status(_resolve_context(brain_dir, context)))
    else:
        output(brain_status(brain_dir))


@brain.command()
@click.argument("context", required=False)
@handle_errors
def validate(context: str | None) -> None:
    """Validate brain structure and index integrity.

    Without arguments, validates all contexts and checks origins against config.
    """
    config = load_config()
    brain_dir = resolve_brain_dir(config)

    findings: list[dict] = []

    if context:
        findings = validate_context(_resolve_context(brain_dir, context))
    else:
        for c in list_contexts(brain_dir):
            findings.extend(validate_context(brain_dir / c))
        findings.extend(validate_origins(brain_dir, config))

    output(findings)
    if any(f["level"] == "error" for f in findings):
        raise SystemExit(1)
