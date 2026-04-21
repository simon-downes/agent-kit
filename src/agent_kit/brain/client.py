"""Brain client — index queries, context management, validation."""

import fcntl
from contextlib import contextmanager
from pathlib import Path

import yaml

ENTITY_DIRS = [
    "me",
    "contacts",
    "projects",
    "knowledge",
    "goals",
    "journal",
    "archive",
]

INDEXABLE_DIRS = ["contacts", "projects", "knowledge", "goals"]

RAW_DIRS = ["inbox", "processing", "completed"]

GITIGNORE_CONTENT = """\
brain.db
.brain.lock
"""


@contextmanager
def _context_lock(context_path: Path):
    """Acquire an exclusive file lock for a brain context."""
    lock_path = context_path / ".brain.lock"
    lock_file = lock_path.open("w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


class BrainClient:
    """Client for brain operations."""

    def __init__(self, brain_dir: Path):
        self._brain_dir = brain_dir

    # --- Public interface ---

    def list_contexts(self) -> list[str]:
        """List context directories in the brain."""
        if not self._brain_dir.exists():
            return []
        return sorted(
            d.name
            for d in self._brain_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
        )

    def init_brain(self, config: dict) -> list[str]:
        """Initialise the brain directory structure."""
        actions = []
        self._brain_dir.mkdir(parents=True, exist_ok=True)

        raw_dir = self._brain_dir / "_raw"
        for subdir in RAW_DIRS:
            path = raw_dir / subdir
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                actions.append(f"created {raw_dir.name}/{subdir}")

        for dirname in ("_inbox", "_outbox", "_memory"):
            path = self._brain_dir / dirname
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                actions.append(f"created {dirname}")

        contexts = self.configured_contexts(config)
        if "shared" not in contexts:
            contexts["shared"] = None

        for name, repo in contexts.items():
            result = self.init_context(name, repo)
            if result:
                actions.append(result)

        return actions

    def init_context(self, name: str, repo: str | None = None) -> str | None:
        """Initialise a single context — clone from repo or create locally."""
        from agent_kit.brain.git import clone_repo, init_local

        validate_name(name)
        context = self._brain_dir / name

        if context.exists():
            return None

        if repo:
            return clone_repo(context, repo)
        return init_local(context)

    def load_index(self, context_path: Path) -> dict:
        """Load index.yaml for a context."""
        index_path = context_path / "index.yaml"
        if not index_path.exists():
            return {}
        try:
            with index_path.open() as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"invalid index.yaml in {context_path.name}: {e}") from e

    def query_index(
        self, index: dict, *, entity_type: str | None = None, slug: str | None = None
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

    def context_status(self, context_path: Path) -> dict:
        """Get status for a context."""
        from agent_kit.brain.git import context_status

        return context_status(context_path)

    def brain_status(self) -> dict:
        """Get overall brain status."""
        result: dict = {"dir": str(self._brain_dir), "contexts": [], "raw": {}}

        raw_dir = self._brain_dir / "_raw"
        for subdir in RAW_DIRS:
            path = raw_dir / subdir
            if path.exists():
                items = sorted(f.name for f in path.iterdir() if not f.name.startswith("."))
                result["raw"][subdir] = items
            else:
                result["raw"][subdir] = []

        for name in self.list_contexts():
            result["contexts"].append(self.context_status(self._brain_dir / name))

        return result

    def validate_context(self, context_path: Path) -> list[dict]:
        """Validate a brain context."""
        findings: list[dict] = []
        context_name = context_path.name

        for subdir in ENTITY_DIRS:
            if not (context_path / subdir).exists():
                findings.append(
                    {
                        "level": "warning",
                        "message": f"missing directory: {subdir}",
                        "context": context_name,
                    }
                )

        index_path = context_path / "index.yaml"
        if not index_path.exists():
            findings.append({"level": "info", "message": "no index.yaml", "context": context_name})
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

        indexed_paths = set()
        for entries in index.values():
            if isinstance(entries, dict):
                for entry in entries.values():
                    if isinstance(entry, dict) and "path" in entry:
                        indexed_paths.add(entry["path"])

        for entity_type in INDEXABLE_DIRS:
            entity_dir = context_path / entity_type
            if not entity_dir.exists():
                continue
            for item in entity_dir.iterdir():
                if item.name.startswith("."):
                    continue
                rel_path = f"{entity_type}/{item.name}" + ("/" if item.is_dir() else "")
                in_index = (
                    rel_path in indexed_paths or f"{entity_type}/{item.name}" in indexed_paths
                )
                if not in_index:
                    findings.append(
                        {
                            "level": "warning",
                            "message": f"not indexed: {rel_path}",
                            "context": context_name,
                        }
                    )

        return findings

    def validate_origins(self, config: dict) -> list[dict]:
        """Check context git origins match configured repos."""
        from agent_kit.brain.git import get_remote_url

        findings: list[dict] = []
        contexts = self.configured_contexts(config)

        for name, expected_repo in contexts.items():
            if not expected_repo:
                continue
            context_path = self._brain_dir / name
            if not context_path.exists():
                findings.append(
                    {
                        "level": "error",
                        "message": f"configured context '{name}' not found — run 'ak brain init'",
                        "context": name,
                    }
                )
                continue

            actual = get_remote_url(context_path)
            if actual is None:
                findings.append(
                    {
                        "level": "warning",
                        "message": "no git remote origin",
                        "context": name,
                    }
                )
            elif actual != expected_repo:
                findings.append(
                    {
                        "level": "warning",
                        "message": f"origin mismatch: expected {expected_repo}, got {actual}",
                        "context": name,
                    }
                )

        return findings

    def reindex_context(self, context_path: Path) -> dict:
        """Rebuild index.yaml for a context."""
        from agent_kit.brain.index import reindex

        return reindex(context_path, _context_lock)

    def commit_context(
        self, context_path: Path, message: str, paths: list[str] | None = None
    ) -> str | None:
        """Stage and commit in a context."""
        from agent_kit.brain.git import commit

        return commit(context_path, message, paths)

    def search(self, query: str, *, context: str | None = None, limit: int = 20) -> list[dict]:
        """Search the brain across index metadata, file content, and memory."""
        from agent_kit.brain.index import _file_mtime
        from agent_kit.brain.search import _match_weight, _rg_search

        query_lower = query.lower()
        terms = query_lower.split()
        seen_paths: set[str] = set()
        results: list[dict] = []

        contexts = [context] if context else self.list_contexts()

        # Phase 1: Index search (weights 1-3)
        for ctx in contexts:
            ctx_path = self._brain_dir / ctx
            index = self.load_index(ctx_path)
            for entity_type, entries in index.items():
                if not isinstance(entries, dict):
                    continue
                for slug, entry in entries.items():
                    if not isinstance(entry, dict):
                        continue

                    rel_path = f"{ctx}/{entry.get('path', '')}"
                    name = entry.get("name", "")
                    summary = entry.get("summary", "")
                    tags = entry.get("tags", [])
                    if not isinstance(tags, list):
                        tags = []

                    weight = _match_weight(terms, name, tags, summary)
                    if weight is None:
                        continue

                    mtime = _file_mtime(ctx_path / entry.get("path", ""))
                    results.append(
                        {
                            "context": ctx,
                            "type": entity_type,
                            "slug": slug,
                            "name": name,
                            "summary": summary,
                            "tags": tags,
                            "path": rel_path,
                            "match": ["", "name", "tag", "summary"][weight],
                            "weight": weight,
                            "modified": mtime,
                        }
                    )
                    seen_paths.add(rel_path)

        # Phase 2: Content search via rg (weight 4)
        rg_paths = [str(self._brain_dir / ctx) for ctx in contexts]
        content_hits = _rg_search(query, rg_paths, self._brain_dir)
        for hit in content_hits:
            if hit["path"] in seen_paths:
                continue
            seen_paths.add(hit["path"])
            hit["weight"] = 4
            hit["match"] = "content"
            results.append(hit)

        # Phase 3: Memory search (weight 5)
        memory_dir = self._brain_dir / "_memory"
        if memory_dir.exists():
            memory_hits = _rg_search(query, [str(memory_dir)], self._brain_dir, context_lines=1)
            for hit in memory_hits:
                if hit["path"] in seen_paths:
                    continue
                seen_paths.add(hit["path"])
                hit["weight"] = 5
                hit["match"] = "memory"
                hit["context"] = "_memory"
                hit["type"] = "memory"
                results.append(hit)

        results.sort(key=lambda r: (r["weight"], -(r.get("modified") or 0)))
        return results[:limit]

    def find_project(self, name: str) -> dict | None:
        """Find a project by directory name across all contexts."""
        from agent_kit.brain.index import _parse_frontmatter

        for context in self.list_contexts():
            readme = self._brain_dir / context / "projects" / name / "README.md"
            if readme.exists():
                frontmatter = _parse_frontmatter(readme)
                frontmatter["context"] = context
                frontmatter["path"] = f"{context}/projects/{name}/"
                return frontmatter
        return None

    @staticmethod
    def configured_contexts(config: dict) -> dict[str, str | None]:
        """Return configured contexts as {name: repo_url_or_none}."""
        brain = config.get("brain", {})
        return brain.get("contexts", {})


# --- Module-level helpers (used by other modules) ---


def resolve_brain_dir(config: dict) -> Path:
    """Resolve brain directory from config."""
    brain = config.get("brain", {})
    return Path(brain.get("dir", "~/.archie/brain")).expanduser()


def validate_name(name: str) -> None:
    """Reject names that could escape the brain directory."""
    if not name or "/" in name or name.startswith(".") or ".." in name:
        raise ValueError(f"invalid context name: {name!r}")


def find_project(brain_dir: Path, name: str) -> dict | None:
    """Module-level convenience for project.py import compatibility."""
    return BrainClient(brain_dir).find_project(name)
