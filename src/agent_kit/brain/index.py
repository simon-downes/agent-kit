"""Brain index operations — metadata extraction, reindexing."""

from pathlib import Path

import yaml

INDEXABLE_DIRS = ["contacts", "projects", "knowledge", "goals"]


def _extract_metadata(path: Path) -> dict:
    """Extract name and summary from a file or directory."""
    if path.is_dir():
        readme = path / "README.md"
        if readme.exists():
            return _parse_frontmatter(readme)
        return {}

    if path.suffix in (".yaml", ".yml"):
        try:
            data = yaml.safe_load(path.read_text()) or {}
            return data if isinstance(data, dict) else {}
        except yaml.YAMLError:
            return {}

    if path.suffix == ".md":
        try:
            return _parse_frontmatter(path)
        except ValueError:
            return {}

    return {}


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


def _slug_to_name(slug: str) -> str:
    """Convert a slug to a human-readable name."""
    return slug.replace("-", " ").replace("_", " ").title()


def _indexable_items(entity_dir: Path) -> list[Path]:
    """List indexable items in an entity directory."""
    items: list[Path] = []
    for item in sorted(entity_dir.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_file():
            items.append(item)
        elif item.is_dir():
            if (item / "README.md").exists():
                items.append(item)
            else:
                for child in sorted(item.rglob("*")):
                    if child.is_file() and not child.name.startswith("."):
                        items.append(child)
    return items


def _file_mtime(path: Path) -> float:
    """Get file modification time, handling dirs and missing files."""
    try:
        if path.is_dir():
            readme = path / "README.md"
            if readme.exists():
                return readme.stat().st_mtime
            return path.stat().st_mtime
        return path.stat().st_mtime
    except OSError:
        return 0.0


def reindex(context_path: Path, lock_fn) -> dict:
    """Rebuild index.yaml for a context from filesystem contents."""
    with lock_fn(context_path):
        existing_index_path = context_path / "index.yaml"
        existing: dict = {}
        if existing_index_path.exists():
            try:
                with existing_index_path.open() as f:
                    existing = yaml.safe_load(f) or {}
            except yaml.YAMLError:
                existing = {}

        index: dict[str, dict] = {}

        for entity_type in INDEXABLE_DIRS:
            entity_dir = context_path / entity_type
            if not entity_dir.exists():
                continue

            entries: dict[str, dict] = {}
            existing_type = existing.get(entity_type, {})

            for item in _indexable_items(entity_dir):
                if item.name.startswith("."):
                    continue

                slug = item.stem if item.is_file() else item.name
                rel_path = str(item.relative_to(context_path))
                if item.is_dir():
                    rel_path += "/"

                if slug in existing_type and existing_type[slug].get("path") == rel_path:
                    entries[slug] = existing_type[slug]
                    continue

                meta = _extract_metadata(item)
                entry: dict = {"name": meta.get("name", _slug_to_name(slug)), "path": rel_path}
                if meta.get("summary"):
                    entry["summary"] = meta["summary"]
                if meta.get("tags"):
                    entry["tags"] = meta["tags"]
                entries[slug] = entry

            if entries:
                index[entity_type] = entries

        index_path = context_path / "index.yaml"
        index_path.write_text(yaml.dump(index, default_flow_style=False, sort_keys=False))
        return index
