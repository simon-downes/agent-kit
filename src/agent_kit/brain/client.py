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
    "archive",
]

RAW_DIRS = ["inbox", "processing", "completed"]

GITIGNORE_CONTENT = """\
brain.db
"""


def resolve_brain_dir(config: dict) -> Path:
    """Resolve brain directory from config."""
    brain = config.get("brain", {})
    return Path(brain.get("dir", "~/.archie/brain")).expanduser()


def configured_contexts(config: dict) -> dict[str, str | None]:
    """Return configured contexts as {name: repo_url_or_none}."""
    brain = config.get("brain", {})
    return brain.get("contexts", {})


def list_contexts(brain_dir: Path) -> list[str]:
    """List context directories in the brain."""
    if not brain_dir.exists():
        return []
    return sorted(
        d.name
        for d in brain_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
    )


def validate_name(name: str) -> None:
    """Reject names that could escape the brain directory."""
    if not name or "/" in name or name.startswith(".") or ".." in name:
        raise ValueError(f"invalid context name: {name!r}")


def init_brain(brain_dir: Path, config: dict) -> list[str]:
    """Initialise the brain directory structure.

    Creates _raw pipeline dirs and initialises/clones all configured contexts.
    Returns list of actions taken.
    """
    actions = []

    brain_dir.mkdir(parents=True, exist_ok=True)

    # Create _raw pipeline directories
    raw_dir = brain_dir / "_raw"
    for subdir in RAW_DIRS:
        path = raw_dir / subdir
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            actions.append(f"created {raw_dir.name}/{subdir}")

    # Ensure shared context exists
    contexts = configured_contexts(config)
    if "shared" not in contexts:
        contexts["shared"] = None

    for name, repo in contexts.items():
        result = init_context(brain_dir, name, repo)
        if result:
            actions.append(result)

    return actions


def init_context(brain_dir: Path, name: str, repo: str | None = None) -> str | None:
    """Initialise a single context — clone from repo or create locally.

    Returns a description of the action taken, or None if already exists.
    """
    validate_name(name)
    context = brain_dir / name

    if context.exists():
        return None

    if repo:
        result = subprocess.run(
            ["git", "clone", repo, str(context)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ValueError(f"git clone failed for {name}: {result.stderr.strip()}")
        return f"cloned {name} from {repo}"

    # Create locally
    for subdir in ENTITY_DIRS:
        (context / subdir).mkdir(parents=True, exist_ok=True)

    (context / ".gitignore").write_text(GITIGNORE_CONTENT)

    result = subprocess.run(["git", "init"], cwd=context, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"git init failed for {name}: {result.stderr.strip()}")

    return f"created {name}"


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
        for etype, entries in index.items():
            if isinstance(entries, dict) and slug in entries:
                return {etype: {slug: entries[slug]}}
        return {}

    if entity_type:
        entries = index.get(entity_type, {})
        return {entity_type: entries} if entries else {}

    return index


def context_status(context_path: Path) -> dict:
    """Get status for a context: git changes."""
    result: dict = {"context": context_path.name}

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

    return result


def brain_status(brain_dir: Path) -> dict:
    """Get overall brain status including _raw pipeline and all contexts."""
    result: dict = {"dir": str(brain_dir), "contexts": [], "raw": {}}

    # Raw pipeline status
    raw_dir = brain_dir / "_raw"
    for subdir in RAW_DIRS:
        path = raw_dir / subdir
        if path.exists():
            items = sorted(f.name for f in path.iterdir() if not f.name.startswith("."))
            result["raw"][subdir] = items
        else:
            result["raw"][subdir] = []

    # Context statuses
    for name in list_contexts(brain_dir):
        result["contexts"].append(context_status(brain_dir / name))

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

    # Check for entities not in the index
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


def validate_origins(brain_dir: Path, config: dict) -> list[dict]:
    """Check context git origins match configured repos."""
    findings: list[dict] = []
    contexts = configured_contexts(config)

    for name, expected_repo in contexts.items():
        if not expected_repo:
            continue
        context_path = brain_dir / name
        if not context_path.exists():
            findings.append(
                {
                    "level": "error",
                    "message": f"configured context '{name}' not found — run 'ak brain init'",
                    "context": name,
                }
            )
            continue

        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=context_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            findings.append(
                {
                    "level": "warning",
                    "message": "no git remote origin",
                    "context": name,
                }
            )
        elif result.stdout.strip() != expected_repo:
            actual = result.stdout.strip()
            findings.append(
                {
                    "level": "warning",
                    "message": f"origin mismatch: expected {expected_repo}, got {actual}",
                    "context": name,
                }
            )

    return findings


def find_project(brain_dir: Path, name: str) -> dict | None:
    """Find a project by directory name across all contexts."""
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
