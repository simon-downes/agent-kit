"""Brain operations — index queries, context management, validation."""

import subprocess
from pathlib import Path

import yaml

ENTITY_DIRS = [
    "me",
    "contacts",
    "projects",
    "knowledge",
    "goals",
    "inbox",
    "outbox",
    "journal",
    "raw",
    "archive",
]

GITIGNORE_CONTENT = """\
raw/
brain.db
"""


def resolve_brain_dir(config: dict) -> Path:
    """Resolve brain directory from config."""
    return Path(config.get("brain_dir", "~/.archie/brain")).expanduser()


def list_contexts(brain_dir: Path) -> list[str]:
    """List context directories in the brain."""
    if not brain_dir.exists():
        return []
    return sorted(d.name for d in brain_dir.iterdir() if d.is_dir() and not d.name.startswith("."))


def validate_name(name: str) -> None:
    """Reject names that could escape the brain directory."""
    if not name or "/" in name or name.startswith(".") or ".." in name:
        raise ValueError(f"invalid context name: {name!r}")


def create_context(brain_dir: Path, name: str) -> Path:
    """Create a brain context with standard directories and git init."""
    validate_name(name)
    context = brain_dir / name
    if context.exists():
        raise ValueError(f"context '{name}' already exists")

    for subdir in ENTITY_DIRS:
        (context / subdir).mkdir(parents=True, exist_ok=True)

    # gitignore for raw/ and brain.db
    (context / ".gitignore").write_text(GITIGNORE_CONTENT)

    # git init
    result = subprocess.run(["git", "init"], cwd=context, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"git init failed: {result.stderr.strip()}")

    return context


def load_index(context_path: Path) -> dict:
    """Load index.yaml for a context. Returns empty dict if missing."""
    index_path = context_path / "index.yaml"
    if not index_path.exists():
        return {}
    try:
        with index_path.open() as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"invalid index.yaml in {context_path.name}: {e}") from e


def query_index(
    index: dict,
    *,
    entity_type: str | None = None,
    slug: str | None = None,
) -> dict:
    """Query the index. Filter by type and/or slug."""
    if slug:
        # Search all types for the slug
        for etype, entries in index.items():
            if isinstance(entries, dict) and slug in entries:
                return {etype: {slug: entries[slug]}}
        return {}

    if entity_type:
        entries = index.get(entity_type, {})
        return {entity_type: entries} if entries else {}

    return index


def context_status(context_path: Path) -> dict:
    """Get status for a context: git changes and unprocessed raw items."""
    result: dict = {"context": context_path.name}

    # Git status
    git_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=context_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if git_result.returncode == 0:
        changes = [line for line in git_result.stdout.strip().splitlines() if line]
        result["changes"] = changes
    else:
        result["changes"] = []
        result["git_error"] = "not a git repository"

    # Raw items
    raw_dir = context_path / "raw"
    if raw_dir.exists():
        raw_items = [f.name for f in raw_dir.iterdir() if not f.name.startswith(".")]
        result["raw"] = sorted(raw_items)
    else:
        result["raw"] = []

    return result


def validate_context(context_path: Path) -> list[dict]:
    """Validate a brain context. Returns a list of findings."""
    findings: list[dict] = []
    context_name = context_path.name

    # Check standard directories exist
    for subdir in ENTITY_DIRS:
        if not (context_path / subdir).exists():
            findings.append(
                {
                    "level": "warning",
                    "message": f"missing directory: {subdir}",
                    "context": context_name,
                }
            )

    # Load and validate index
    index_path = context_path / "index.yaml"
    if not index_path.exists():
        findings.append(
            {
                "level": "info",
                "message": "no index.yaml",
                "context": context_name,
            }
        )
        return findings

    try:
        index = yaml.safe_load(index_path.read_text()) or {}
    except yaml.YAMLError as e:
        findings.append(
            {
                "level": "error",
                "message": f"invalid index.yaml: {e}",
                "context": context_name,
            }
        )
        return findings

    # Check index entries point to existing paths
    for entity_type, entries in index.items():
        if not isinstance(entries, dict):
            findings.append(
                {
                    "level": "error",
                    "message": f"index.{entity_type} is not a mapping",
                    "context": context_name,
                }
            )
            continue

        for slug, entry in entries.items():
            if not isinstance(entry, dict):
                findings.append(
                    {
                        "level": "error",
                        "message": f"index.{entity_type}.{slug} is not a mapping",
                        "context": context_name,
                    }
                )
                continue

            path = entry.get("path")
            if not path:
                findings.append(
                    {
                        "level": "error",
                        "message": f"index.{entity_type}.{slug} missing 'path'",
                        "context": context_name,
                    }
                )
            elif not (context_path / path).exists():
                findings.append(
                    {
                        "level": "error",
                        "message": f"index.{entity_type}.{slug} path not found: {path}",
                        "context": context_name,
                    }
                )

            if "name" not in entry:
                findings.append(
                    {
                        "level": "warning",
                        "message": f"index.{entity_type}.{slug} missing 'name'",
                        "context": context_name,
                    }
                )

    # Check for entities not in the index (only types that should be indexed)
    indexed_paths = set()
    for entries in index.values():
        if isinstance(entries, dict):
            for entry in entries.values():
                if isinstance(entry, dict) and "path" in entry:
                    indexed_paths.add(entry["path"])

    for entity_type in ["contacts", "projects", "knowledge", "goals"]:
        entity_dir = context_path / entity_type
        if not entity_dir.exists():
            continue
        for item in entity_dir.iterdir():
            if item.name.startswith("."):
                continue
            rel_path = f"{entity_type}/{item.name}" + ("/" if item.is_dir() else "")
            if rel_path not in indexed_paths and f"{entity_type}/{item.name}" not in indexed_paths:
                findings.append(
                    {
                        "level": "warning",
                        "message": f"not indexed: {rel_path}",
                        "context": context_name,
                    }
                )

    return findings


def find_project(brain_dir: Path, name: str) -> dict | None:
    """Find a project by directory name across all contexts.

    Scans */projects/<name>/README.md, parses YAML frontmatter, returns
    the frontmatter dict with 'context' and 'path' added. Returns None if not found.
    """
    for context in list_contexts(brain_dir):
        readme = brain_dir / context / "projects" / name / "README.md"
        if readme.exists():
            frontmatter = _parse_frontmatter(readme)
            frontmatter["context"] = context
            frontmatter["path"] = f"{context}/projects/{name}/"
            return frontmatter
    return None


def _parse_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}
    end = text.index("\n---\n", 4)
    try:
        return yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return {}
