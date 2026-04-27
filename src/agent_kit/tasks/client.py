"""Task runner client — DB operations and task execution."""

import json
import sqlite3
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from agent_kit.config import load_config
from agent_kit.tasks.db import get_connection

_LOG_DIR = Path("~/.agent-kit/tasks/logs").expanduser()
_DEFAULT_INACTIVITY_TIMEOUT = 600
_POLL_INTERVAL = 5
_TERM_GRACE_PERIOD = 10
_MAX_WORKERS = 4


class TaskClient:
    """Client for task lifecycle management."""

    def __init__(self, db_path: Path | None = None):
        self._db_path = db_path
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

    def run(self) -> list[dict]:
        """Claim and execute pending tasks. Returns list of completed task dicts."""
        timeout = self._load_timeout()
        self._timeout_orphans(timeout)
        claimed = self._claim_pending()
        if not claimed:
            return []
        self._log_dir.mkdir(parents=True, exist_ok=True)
        results = []
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = {executor.submit(self._execute_task, task, timeout): task for task in claimed}
            for future in futures:
                results.append(future.result())
        return results

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

    def _load_timeout(self) -> int:
        """Load inactivity timeout from config."""
        config = load_config()
        return config.get("tasks", {}).get("inactivity_timeout", _DEFAULT_INACTIVITY_TIMEOUT)

    def _timeout_orphans(self, timeout: int) -> None:
        """Mark running tasks as timed out if their logs are stale."""
        rows = self._conn.execute("SELECT * FROM tasks WHERE status = 'running'").fetchall()
        now = time.time()
        for row in rows:
            task = self._row_to_dict(row)
            log = self._log_path(task)
            if log.exists():
                last_activity = log.stat().st_mtime
            elif task["started_at"]:
                last_activity = datetime.fromisoformat(task["started_at"]).timestamp()
            else:
                last_activity = now
            if now - last_activity > timeout:
                self._finish_task(
                    self._conn, task["id"], "timeout", error=f"no log activity for {timeout}s"
                )

    def _claim_pending(self) -> list[dict]:
        """Atomically claim all pending tasks."""
        rows = self._conn.execute(
            "UPDATE tasks SET status = 'running', started_at = ? "
            "WHERE status = 'pending' RETURNING *",
            (datetime.now(UTC).isoformat(),),
        ).fetchall()
        self._conn.commit()
        return [self._row_to_dict(r) for r in rows]

    def _execute_task(self, task: dict, timeout: int) -> dict:
        """Run a single task, monitoring for timeout and cancellation."""
        conn = get_connection(self._db_path)
        stdout_log = self._log_path(task)
        stderr_log = self._log_path(task, error=True)
        with open(stdout_log, "w") as out, open(stderr_log, "w") as err:
            try:
                proc = subprocess.Popen([task["command"], *task["args"]], stdout=out, stderr=err)
            except OSError as e:
                self._finish_task(conn, task["id"], "failed", exit_code=1, error=str(e))
                return self._fetch_task(conn, task["id"])

            while proc.poll() is None:
                time.sleep(_POLL_INTERVAL)
                # Check for external cancellation
                row = conn.execute(
                    "SELECT status FROM tasks WHERE id = ?", (task["id"],)
                ).fetchone()
                if row and row["status"] == "cancelled":
                    self._terminate(proc)
                    self._finish_task(conn, task["id"], "cancelled", error="cancelled by user")
                    return self._fetch_task(conn, task["id"])
                # Check for inactivity timeout
                if stdout_log.exists() and time.time() - stdout_log.stat().st_mtime > timeout:
                    self._terminate(proc)
                    self._finish_task(
                        conn, task["id"], "timeout", error=f"no log activity for {timeout}s"
                    )
                    return self._fetch_task(conn, task["id"])

        exit_code = proc.returncode
        status = "done" if exit_code == 0 else "failed"
        error = None if exit_code == 0 else f"exit code {exit_code}"
        self._finish_task(conn, task["id"], status, exit_code=exit_code, error=error)
        return self._fetch_task(conn, task["id"])

    def _terminate(self, proc: subprocess.Popen) -> None:
        """Gracefully terminate a process: SIGTERM, then SIGKILL after grace period."""
        proc.terminate()
        try:
            proc.wait(timeout=_TERM_GRACE_PERIOD)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    def _finish_task(
        self,
        conn: sqlite3.Connection,
        task_id: int,
        status: str,
        *,
        exit_code: int | None = None,
        error: str | None = None,
    ) -> None:
        """Update a task to a terminal state."""
        now = datetime.now(UTC).isoformat()
        conn.execute(
            "UPDATE tasks SET status = ?, finished_at = ?, exit_code = ?, error = ? WHERE id = ?",
            (status, now, exit_code, error, task_id),
        )
        conn.commit()

    def _fetch_task(self, conn: sqlite3.Connection, task_id: int) -> dict:
        """Fetch a task using a specific connection (thread-safe)."""
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise ValueError(f"task {task_id} not found")
        return self._row_to_dict(row)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Convert a sqlite3.Row to a dict with args parsed from JSON."""
        d = dict(row)
        d["args"] = json.loads(d["args"])
        return d
