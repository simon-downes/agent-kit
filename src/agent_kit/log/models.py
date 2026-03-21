"""Data models and validation for activity log."""

import json
import re
from dataclasses import dataclass

ENTRY_KINDS = [
    "task",
    "decision",
    "change",
    "issue",
    "note",
    "request",
]

KEBAB_CASE_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass
class Entry:
    """Activity log entry."""

    id: int
    ts: str
    project: str
    kind: str
    topic: str | None
    ref: str | None
    summary: str
    metadata: str


def validate_kebab_case(value: str) -> None:
    """Validate that a string is in lower-kebab-case format.

    Raises:
        ValueError: If the string is not in valid kebab-case format.
    """
    if not KEBAB_CASE_PATTERN.match(value):
        raise ValueError(
            f"'{value}' must be in lower-kebab-case format (e.g., 'my-project', 'api-design')"
        )


def validate_kind(kind: str) -> None:
    """Validate that kind is in the allowed list.

    Raises:
        ValueError: If kind is not in ENTRY_KINDS.
    """
    if kind not in ENTRY_KINDS:
        kinds_str = ", ".join(ENTRY_KINDS)
        raise ValueError(f"Invalid kind '{kind}'. Must be one of: {kinds_str}")


def validate_metadata(metadata: str) -> None:
    """Validate that metadata is valid JSON or empty string.

    Raises:
        ValueError: If metadata is not valid JSON.
    """
    if metadata and metadata.strip():
        try:
            json.loads(metadata)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON metadata: {e}")
