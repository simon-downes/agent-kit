"""Brain search operations — index matching, ripgrep integration."""

import subprocess
from pathlib import Path


def _match_weight(terms: list[str], name: str, tags: list[str], summary: str) -> int | None:
    """Return match weight (1-3) or None if no match."""
    name_lower = name.lower()
    tags_lower = [t.lower() for t in tags]
    summary_lower = summary.lower()

    if any(t in name_lower for t in terms):
        return 1
    if any(t in tags_lower for t in terms):
        return 2
    if any(t in summary_lower for t in terms):
        return 3
    return None


def _rg_search(
    query: str,
    paths: list[str],
    brain_dir: Path,
    *,
    context_lines: int = 0,
) -> list[dict]:
    """Run rg and return deduplicated file-level results."""
    from agent_kit.brain.index import _file_mtime

    cmd = [
        "rg",
        "-i",
        "-l",
        "--glob",
        "!.git",
        "--glob",
        "!_raw",
        "--glob",
        "!brain.db",
        "--glob",
        "!.brain.lock",
        "-t",
        "md",
        "-t",
        "yaml",
        query,
    ] + paths

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []

    hits: list[dict] = []
    for line in result.stdout.strip().splitlines():
        filepath = Path(line)
        try:
            rel = str(filepath.relative_to(brain_dir))
        except ValueError:
            rel = line
        mtime = _file_mtime(filepath)

        entry: dict = {
            "path": rel,
            "name": filepath.stem.replace("-", " ").replace("_", " ").title(),
            "modified": mtime,
        }

        if context_lines >= 0:
            excerpt = _rg_excerpt(query, str(filepath))
            if excerpt:
                entry["excerpt"] = excerpt

        hits.append(entry)

    return hits


def _rg_excerpt(query: str, filepath: str) -> str | None:
    """Get a short excerpt around the first match in a file."""
    result = subprocess.run(
        ["rg", "-i", "-m", "1", "-C", "1", query, filepath],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    lines = result.stdout.strip().splitlines()
    return " ".join(line.strip() for line in lines[:3] if line.strip())[:200]
