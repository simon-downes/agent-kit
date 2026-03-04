"""Database operations for kv store."""

import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path


def get_db_path() -> Path:
    """Get the database path from env var or default."""
    db_path = os.environ.get("KV_DB")
    if db_path:
        return Path(db_path)
    return Path.home() / ".cli-tools" / "kv" / "db"


def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize database and return connection."""
    is_new = not db_path.exists()

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kv (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            expires_at DATETIME
        )
        """)
    conn.commit()

    if is_new:
        os.chmod(db_path, 0o600)

    return conn


def validate_key(key: str) -> bool:
    """Validate key is lower-kebab-case and <= 100 chars."""
    if len(key) > 100:
        return False
    return bool(re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", key))


def set_value(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Set a key-value pair."""
    conn.execute(
        "INSERT OR REPLACE INTO kv (key, value, expires_at) VALUES (?, ?, NULL)",
        (key, value),
    )
    conn.commit()


def get_value(conn: sqlite3.Connection, key: str) -> tuple[str | None, bool]:
    """Get value for key. Returns (value, is_expired)."""
    cursor = conn.execute(
        "SELECT value, expires_at FROM kv WHERE key = ?",
        (key,),
    )
    row = cursor.fetchone()

    if row is None:
        return None, False

    value, expires_at = row
    if expires_at:
        expiry = datetime.fromisoformat(expires_at)
        if expiry < datetime.now():
            return value, True

    return value, False


def list_keys(conn: sqlite3.Connection) -> list[tuple[str, str | None]]:
    """List all keys with their expiry times."""
    cursor = conn.execute("SELECT key, expires_at FROM kv ORDER BY key")
    return cursor.fetchall()


def set_expiry(conn: sqlite3.Connection, key: str, ttl: int) -> bool:
    """Set expiry for a key. Returns True if key exists."""
    expires_at = datetime.now().timestamp() + ttl
    expires_dt = datetime.fromtimestamp(expires_at)

    cursor = conn.execute(
        "UPDATE kv SET expires_at = ? WHERE key = ?",
        (expires_dt.isoformat(), key),
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_key(conn: sqlite3.Connection, key: str) -> bool:
    """Delete a key. Returns True if key existed."""
    cursor = conn.execute("DELETE FROM kv WHERE key = ?", (key,))
    conn.commit()
    return cursor.rowcount > 0


def clean_expired(conn: sqlite3.Connection) -> int:
    """Remove expired entries. Returns count of deleted entries."""
    now = datetime.now().isoformat()
    cursor = conn.execute("DELETE FROM kv WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))
    conn.commit()
    return cursor.rowcount
