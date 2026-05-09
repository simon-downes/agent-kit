"""Task database — connection management and schema."""

import sqlite3
from pathlib import Path

_DEFAULT_DB_PATH = Path("~/.agent-kit/tasks.db").expanduser()

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    command     TEXT NOT NULL,
    args        TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    started_at  TEXT,
    finished_at TEXT,
    exit_code   INTEGER,
    error       TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_active_name
    ON tasks(name) WHERE status IN ('pending', 'running');
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and schema initialised."""
    path = db_path or _DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn
