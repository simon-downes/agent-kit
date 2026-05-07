"""Brain client — search, index, reference tracking."""

import fcntl
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

import yaml

# Directories excluded from search and indexing
EXCLUDED_DIRS = {"_raw", "_archie", ".git"}


@contextmanager
def _brain_lock(brain_dir: Path):
    """Acquire an exclusive file lock for the brain."""
    lock_path = brain_dir / ".brain.lock"
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

    # --- Search ---

    def search(self, terms: list[str], *, limit: int = 10) -> list[dict]:
        """Search brain with multiple terms, return ranked results."""
        import re
        from datetime import date, datetime

        from agent_kit.brain.index import _file_mtime
        from agent_kit.brain.search import _rg_search

        results: dict[str, dict] = {}

        # Phase 1: Index search
        index = self.load_index()
        for entity_type, entries in index.items():
            if not isinstance(entries, dict):
                continue
            for slug, entry in entries.items():
                if not isinstance(entry, dict):
                    continue
                path = entry.get("path", "")
                name = entry.get("name", "")
                tags = entry.get("tags", []) if isinstance(entry.get("tags"), list) else []
                summary = entry.get("summary", "")

                for term in terms:
                    t = term.lower()
                    score = 0
                    if t in name.lower() or t in slug.lower():
                        score = 3
                    elif any(t in tag.lower() for tag in tags):
                        score = 2
                    elif t in summary.lower():
                        score = 1
                    if score:
                        if path not in results:
                            results[path] = {
                                "path": path,
                                "name": name,
                                "score": 0,
                                "matches": 0,
                                "type": entity_type,
                                "modified": _file_mtime(self._brain_dir / path),
                            }
                        results[path]["score"] += score
                        results[path]["matches"] += 1

        # Phase 2: Content search via rg
        search_paths = [
            str(d) for d in self._brain_dir.iterdir() if d.is_dir() and d.name not in EXCLUDED_DIRS
        ]
        # Include _archie/memory/ explicitly (excluded from general iterdir walk)
        memory_dir = self._brain_dir / "_archie" / "memory"
        if memory_dir.is_dir():
            search_paths.append(str(memory_dir))

        if search_paths:
            for term in terms:
                hits = _rg_search(term, search_paths, self._brain_dir)
                for hit in hits:
                    path = hit["path"]
                    if path not in results:
                        results[path] = {
                            "path": path,
                            "name": hit.get("name", ""),
                            "score": 0,
                            "matches": 0,
                            "modified": hit.get("modified"),
                        }
                    results[path]["score"] += 1
                    results[path]["matches"] += 1
                    if hit.get("excerpt") and "excerpt" not in results[path]:
                        results[path]["excerpt"] = hit["excerpt"]

        # Phase 3: Age decay for memory results
        today = date.today()
        date_re = re.compile(r"(\d{4}-\d{2}-\d{2})")
        for result in results.values():
            if result.get("type") != "memory":
                continue
            match = date_re.search(result["path"])
            if not match:
                continue
            try:
                file_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
            except ValueError:
                continue
            age_days = (today - file_date).days
            if age_days < 7:
                result["score"] += 2
            elif age_days < 30:
                result["score"] += 1
            elif age_days > 90:
                result["score"] -= 1

        ranked = sorted(results.values(), key=lambda r: (-r["matches"], -r["score"]))
        return ranked[:limit]

    # --- Index ---

    def load_index(self) -> dict:
        """Load index.yaml from the brain root."""
        index_path = self._brain_dir / "index.yaml"
        if not index_path.exists():
            return {}
        try:
            with index_path.open() as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"invalid index.yaml: {e}") from e

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

    def reindex(self) -> dict:
        """Rebuild index.yaml for the brain."""
        from agent_kit.brain.index import reindex

        return reindex(self._brain_dir, _brain_lock)

    # --- Reference Tracking ---

    def record_ref(self, path: str) -> None:
        """Record a brain entry access."""
        db = self._get_db()
        db.execute("INSERT INTO refs (path, ts) VALUES (?, ?)", (path, int(time.time())))
        db.commit()
        db.close()

    def top_refs(self, limit: int = 10) -> list[dict]:
        """Return most-referenced entries."""
        db = self._get_db()
        rows = db.execute(
            "SELECT path, COUNT(*) as count FROM refs GROUP BY path ORDER BY count DESC LIMIT ?",
            (limit,),
        ).fetchall()
        db.close()
        return [{"path": r[0], "count": r[1]} for r in rows]

    def stale_refs(self, since_days: int = 90) -> list[dict]:
        """Return entries not referenced within N days."""
        cutoff = int(time.time()) - (since_days * 86400)
        db = self._get_db()
        # Find all indexed paths that have no ref after cutoff
        index = self.load_index()
        all_paths = set()
        for entries in index.values():
            if isinstance(entries, dict):
                for entry in entries.values():
                    if isinstance(entry, dict) and "path" in entry:
                        all_paths.add(entry["path"])

        recent_paths = {
            r[0]
            for r in db.execute("SELECT DISTINCT path FROM refs WHERE ts > ?", (cutoff,)).fetchall()
        }
        db.close()

        stale = all_paths - recent_paths
        return [{"path": p} for p in sorted(stale)]

    def _get_db(self) -> sqlite3.Connection:
        """Get or create the brain SQLite database."""
        db_path = self._brain_dir / "brain.db"
        db = sqlite3.connect(db_path)
        db.execute("CREATE TABLE IF NOT EXISTS refs (path TEXT NOT NULL, ts INTEGER NOT NULL)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_refs_path ON refs(path)")
        return db

    # --- Status ---

    def brain_status(self) -> dict:
        """Get brain status."""
        from agent_kit.brain.git import git_status

        result: dict = {"dir": str(self._brain_dir)}

        if self._brain_dir.exists():
            result["git"] = git_status(self._brain_dir)
            dirs = sorted(
                d.name
                for d in self._brain_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            )
            result["directories"] = dirs
        else:
            result["exists"] = False

        return result

    # --- Commit ---

    def commit(self, message: str, paths: list[str] | None = None) -> str | None:
        """Stage and commit in the brain."""
        from agent_kit.brain.git import commit

        return commit(self._brain_dir, message, paths)

    # --- Project lookup ---

    def find_project(self, name: str) -> dict | None:
        """Find a project by directory name."""
        from agent_kit.brain.index import _parse_frontmatter

        # Check projects/<name>/README.md or projects/<name>.md
        readme = self._brain_dir / "projects" / name / "README.md"
        if readme.exists():
            frontmatter = _parse_frontmatter(readme)
            frontmatter["path"] = f"projects/{name}/"
            return frontmatter

        single = self._brain_dir / "projects" / f"{name}.md"
        if single.exists():
            frontmatter = _parse_frontmatter(single)
            frontmatter["path"] = f"projects/{name}.md"
            return frontmatter

        return None


# --- Module-level helpers ---


def resolve_brain_dir(config: dict) -> Path:
    """Resolve brain directory from config."""
    brain = config.get("brain", {})
    return Path(brain.get("dir", "~/.archie/brain")).expanduser()


def validate_name(name: str) -> None:
    """Reject names that could escape the brain directory."""
    if not name or "/" in name or name.startswith(".") or ".." in name:
        raise ValueError(f"invalid name: {name!r}")
