"""Task runner client — DB operations and task execution."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from agent_kit.tasks.db import get_connection


class TaskClient:
    """Client for task lifecycle management."""

    def __init__(self, db_path: Path | None = None):
        self._conn = get_connection(db_path)

    # --- Public interface ---

    def create(self, name: str, command: str, args: list[str]) -> dict:
        """Create a pending task. Returns the task as a dict."""
        now = datetime.now(UTC).isoformat()
        try:
            cursor = self._conn.execute(
                "INSERT INTO tasks (name, command, args, created_at) VALUES (?, ?, ?, ?)",
                (name, command, json.dumps(args), now),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"task '{name}' is already pending or running")
        return self._get_by_id(cursor.lastrowid)

    # --- Private implementation ---

    def _get_by_id(self, task_id: int) -> dict:
        """Fetch a task by ID."""
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise ValueError(f"task {task_id} not found")
        return self._row_to_dict(row)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Convert a sqlite3.Row to a dict with args parsed from JSON."""
        d = dict(row)
        d["args"] = json.loads(d["args"])
        return d
