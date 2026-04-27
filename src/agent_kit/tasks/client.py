"""Task runner client — DB operations and task execution."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from agent_kit.tasks.db import get_connection

_LOG_DIR = Path("~/.agent-kit/tasks/logs").expanduser()


class TaskClient:
    """Client for task lifecycle management."""

    def __init__(self, db_path: Path | None = None):
        self._conn = get_connection(db_path)
        self._log_dir = _LOG_DIR

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

    def list_tasks(
        self,
        *,
        status: str | None = None,
        show_all: bool = False,
        limit: int = 20,
    ) -> list[dict]:
        """List tasks. Default shows pending/running only."""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at ASC LIMIT ?",
                (status, limit),
            ).fetchall()
        elif show_all:
            rows = self._conn.execute(
                "SELECT * FROM tasks ORDER BY created_at ASC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE status IN ('pending', 'running') "
                "ORDER BY created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get(self, name_or_id: str) -> dict:
        """Look up a task by name (exact match) or ID. Raises ValueError if not found."""
        # Try name first
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE name = ? ORDER BY id DESC LIMIT 1",
            (name_or_id,),
        ).fetchone()
        if row:
            return self._row_to_dict(row)
        # Try ID
        try:
            task_id = int(name_or_id)
        except ValueError:
            raise ValueError(f"task '{name_or_id}' not found")
        return self._get_by_id(task_id)

    def get_log_path(self, name_or_id: str, *, error: bool = False) -> Path:
        """Get the log file path for a task. Raises ValueError if task not found."""
        task = self.get(name_or_id)
        return self._log_path(task, error=error)

    def cancel(self, name_or_id: str) -> dict:
        """Cancel a pending or running task. Returns the updated task."""
        task = self.get(name_or_id)
        if task["status"] in ("done", "failed", "timeout", "cancelled"):
            raise ValueError(f"task '{task['name']}' already completed ({task['status']})")
        now = datetime.now(UTC).isoformat()
        error = "cancelled by user" if task["status"] == "running" else None
        self._conn.execute(
            "UPDATE tasks SET status = 'cancelled', finished_at = ?, error = ? WHERE id = ?",
            (now, error, task["id"]),
        )
        self._conn.commit()
        return self._get_by_id(task["id"])

    # --- Private implementation ---

    def _get_by_id(self, task_id: int) -> dict:
        """Fetch a task by ID."""
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise ValueError(f"task {task_id} not found")
        return self._row_to_dict(row)

    def _log_path(self, task: dict, *, error: bool = False) -> Path:
        """Derive log file path from task name and ID."""
        suffix = ".error.log" if error else ".log"
        return self._log_dir / f"{task['name']}-{task['id']}{suffix}"

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Convert a sqlite3.Row to a dict with args parsed from JSON."""
        d = dict(row)
        d["args"] = json.loads(d["args"])
        return d
