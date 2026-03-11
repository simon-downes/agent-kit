"""Database operations for agent memory."""

import sqlite3
from pathlib import Path


def get_db_path() -> Path:
    """Get the database file path."""
    db_dir = Path.home() / ".agent-kit" / "mem"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "db"


def get_connection() -> sqlite3.Connection:
    """Get database connection and ensure schema is initialized."""
    db_path = get_db_path()
    conn = sqlite3.Connection(db_path)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema and indexes."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            project TEXT NOT NULL,
            kind TEXT NOT NULL,
            topic TEXT,
            ref TEXT,
            summary TEXT NOT NULL,
            metadata TEXT DEFAULT ''
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_project_ts
        ON memories(project, ts DESC)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_project_kind
        ON memories(project, kind)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_project_topic
        ON memories(project, topic)
    """)

    conn.commit()


def add_memory(
    project: str,
    kind: str,
    summary: str,
    topic: str | None = None,
    ref: str | None = None,
    metadata: str = "",
) -> int:
    """Add a memory and return its ID."""
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO memories (project, kind, topic, ref, summary, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (project, kind, topic, ref, summary, metadata),
    )
    memory_id = cursor.lastrowid
    if memory_id is None:
        raise RuntimeError("Failed to get memory ID after insert")
    conn.commit()
    conn.close()
    return memory_id


def list_memories(
    project: str,
    kind: str | None = None,
    topic: str | None = None,
    limit: int = 25,
) -> list[sqlite3.Row]:
    """List memories for a project with optional filters."""
    conn = get_connection()

    query = "SELECT * FROM memories WHERE project = ?"
    params: list[str | int] = [project]

    if kind:
        query += " AND kind = ?"
        params.append(kind)

    if topic:
        query += " AND topic = ?"
        params.append(topic)

    query += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)

    cursor = conn.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results


def get_stats(project: str) -> dict[str, dict[str, int]]:
    """Get statistics for a project."""
    conn = get_connection()

    # Count by kind
    cursor = conn.execute(
        """
        SELECT kind, COUNT(*) as count
        FROM memories
        WHERE project = ?
        GROUP BY kind
        ORDER BY count DESC
        """,
        (project,),
    )
    by_kind = {row["kind"]: row["count"] for row in cursor.fetchall()}

    # Recent activity
    cursor = conn.execute(
        """
        SELECT
            COUNT(CASE WHEN ts >= datetime('now', '-7 days') THEN 1 END) as last_7_days,
            COUNT(CASE WHEN ts >= datetime('now', '-30 days') THEN 1 END) as last_30_days,
            COUNT(*) as total
        FROM memories
        WHERE project = ?
        """,
        (project,),
    )
    activity = dict(cursor.fetchone())

    conn.close()

    return {
        "by_kind": by_kind,
        "activity": activity,
    }
