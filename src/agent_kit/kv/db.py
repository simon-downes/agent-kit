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
    return Path.home() / ".agent-kit" / "db"


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


# Public API - simplified interface without requiring connection management


def get(key: str) -> str | None:
    """Get value for key. Returns None if not found or expired."""
    db_path = get_db_path()
    conn = init_db(db_path)
    try:
        value, is_expired = get_value(conn, key)
        if is_expired:
            delete_key(conn, key)
            return None
        return value
    finally:
        conn.close()


def set(key: str, value: str) -> None:
    """Set a key-value pair."""
    if not validate_key(key):
        raise ValueError(f"Invalid key: {key}")
    db_path = get_db_path()
    conn = init_db(db_path)
    try:
        set_value(conn, key, value)
    finally:
        conn.close()


def delete(key: str) -> bool:
    """Delete a key. Returns True if key existed."""
    db_path = get_db_path()
    conn = init_db(db_path)
    try:
        return delete_key(conn, key)
    finally:
        conn.close()


def list_all() -> list[tuple[str, str | None]]:
    """List all keys with their expiry times."""
    db_path = get_db_path()
    conn = init_db(db_path)
    try:
        return list_keys(conn)
    finally:
        conn.close()


def clean_expired_keys() -> int:
    """Remove expired entries. Returns count of deleted entries."""
    db_path = get_db_path()
    conn = init_db(db_path)
    try:
        return clean_expired(conn)
    finally:
        conn.close()


def expire(key: str, ttl: int) -> bool:
    """Set expiry for a key. Returns True if key exists."""
    db_path = get_db_path()
    conn = init_db(db_path)
    try:
        return set_expiry(conn, key, ttl)
    finally:
        conn.close()
