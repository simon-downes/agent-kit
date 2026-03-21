"""Database operations for activity log."""

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def get_db_path() -> Path:
    """Get the database file path."""
    db_dir = Path.home() / ".agent-kit" / "log"
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
        CREATE TABLE IF NOT EXISTS entries (
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
        ON entries(project, ts DESC)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_project_kind
        ON entries(project, kind)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_project_topic
        ON entries(project, topic)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ts
        ON entries(ts DESC)
    """)

    conn.commit()


def _parse_relative_date(value: str) -> str:
    """Parse a relative date string (e.g., '7d', '4w') into an ISO date.

    Supports: Nd (days), Nw (weeks)

    Raises:
        ValueError: If the format is not recognized.
    """
    match = re.match(r"^(\d+)([dw])$", value)
    if not match:
        raise ValueError(f"Invalid relative date '{value}'. Use format like '7d' or '4w'.")

    amount = int(match.group(1))
    unit = match.group(2)

    now = datetime.now(timezone.utc)
    if unit == "d":
        dt = now - timedelta(days=amount)
    else:  # "w"
        dt = now - timedelta(weeks=amount)

    return dt.strftime("%Y-%m-%d")


def parse_date_filter(value: str) -> str:
    """Parse a date filter value — either ISO date or relative format.

    Returns an ISO date string suitable for SQL comparison.
    """
    # Try ISO date first
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError:
        pass

    return _parse_relative_date(value)


def add_entry(
    project: str,
    kind: str,
    summary: str,
    topic: str | None = None,
    ref: str | None = None,
    metadata: str = "",
) -> int:
    """Add a log entry and return its ID."""
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO entries (project, kind, topic, ref, summary, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (project, kind, topic, ref, summary, metadata),
    )
    entry_id = cursor.lastrowid
    if entry_id is None:
        raise RuntimeError("Failed to get entry ID after insert")
    conn.commit()
    conn.close()
    return entry_id


def list_entries(
    project: str | None = None,
    kind: str | None = None,
    topic: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 25,
) -> list[sqlite3.Row]:
    """List log entries with optional filters.

    Args:
        project: Filter by project (optional — omit for cross-project query).
        kind: Filter by entry kind.
        topic: Filter by topic.
        since: Only entries on or after this date (ISO or relative).
        until: Only entries on or before this date (ISO or relative).
        limit: Maximum number of results.
    """
    conn = get_connection()

    query = "SELECT * FROM entries WHERE 1=1"
    params: list[str | int] = []

    if project:
        query += " AND project = ?"
        params.append(project)

    if kind:
        query += " AND kind = ?"
        params.append(kind)

    if topic:
        query += " AND topic = ?"
        params.append(topic)

    if since:
        query += " AND ts >= ?"
        params.append(parse_date_filter(since))

    if until:
        query += " AND ts <= ?"
        params.append(parse_date_filter(until) + " 23:59:59")

    query += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)

    cursor = conn.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results


def get_stats(project: str | None = None) -> dict[str, dict[str, int]]:
    """Get statistics, optionally filtered by project."""
    conn = get_connection()

    where = "WHERE project = ?" if project else ""
    params: list[str] = [project] if project else []

    # Count by kind
    cursor = conn.execute(
        f"""
        SELECT kind, COUNT(*) as count
        FROM entries
        {where}
        GROUP BY kind
        ORDER BY count DESC
        """,
        params,
    )
    by_kind = {row["kind"]: row["count"] for row in cursor.fetchall()}

    # Recent activity
    cursor = conn.execute(
        f"""
        SELECT
            COUNT(CASE WHEN ts >= datetime('now', '-7 days') THEN 1 END) as last_7_days,
            COUNT(CASE WHEN ts >= datetime('now', '-30 days') THEN 1 END) as last_30_days,
            COUNT(*) as total
        FROM entries
        {where}
        """,
        params,
    )
    activity = dict(cursor.fetchone())

    # Project counts (cross-project only)
    by_project: dict[str, int] = {}
    if not project:
        cursor = conn.execute("""
            SELECT project, COUNT(*) as count
            FROM entries
            GROUP BY project
            ORDER BY count DESC
        """)
        by_project = {row["project"]: row["count"] for row in cursor.fetchall()}

    conn.close()

    return {
        "by_kind": by_kind,
        "activity": activity,
        "by_project": by_project,
    }
