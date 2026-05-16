"""Brain search operations — ripgrep integration."""

import subprocess
from pathlib import Path

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "it",
        "as",
        "be",
        "was",
        "are",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "this",
        "that",
        "these",
        "those",
        "not",
        "no",
        "so",
        "if",
        "then",
    }
)


def _split_words(term: str) -> list[str]:
    """Split a multi-word term into individual words with stopwords removed."""
    words = [w for w in term.lower().split() if w not in STOPWORDS]
    return words if words else term.lower().split()


def _rg_search(
    query: str,
    paths: list[str],
    brain_dir: Path,
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
