"""Tests for kv database operations."""

import tempfile
from pathlib import Path

import pytest
from agent_kit.kv.db import (
    clean_expired,
    delete_key,
    get_value,
    init_db,
    list_keys,
    set_expiry,
    set_value,
    validate_key,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = init_db(db_path)
    yield conn
    conn.close()
    db_path.unlink()


def test_validate_key():
    """Test key validation."""
    assert validate_key("valid-key")
    assert validate_key("a")
    assert validate_key("key-with-numbers-123")
    assert not validate_key("UPPERCASE")
    assert not validate_key("has_underscore")
    assert not validate_key("has space")
    assert not validate_key("-starts-with-dash")
    assert not validate_key("ends-with-dash-")
    assert not validate_key("a" * 101)


def test_set_and_get(temp_db):
    """Test setting and getting values."""
    set_value(temp_db, "test-key", "test-value")
    value, is_expired = get_value(temp_db, "test-key")
    assert value == "test-value"
    assert not is_expired


def test_get_nonexistent(temp_db):
    """Test getting nonexistent key."""
    value, is_expired = get_value(temp_db, "nonexistent")
    assert value is None
    assert not is_expired


def test_set_overwrites(temp_db):
    """Test that set overwrites existing values."""
    set_value(temp_db, "key", "value1")
    set_value(temp_db, "key", "value2")
    value, _ = get_value(temp_db, "key")
    assert value == "value2"


def test_list_keys(temp_db):
    """Test listing keys."""
    set_value(temp_db, "zebra", "last")
    set_value(temp_db, "alpha", "first")
    set_value(temp_db, "middle", "mid")

    keys = list_keys(temp_db)
    assert len(keys) == 3
    assert keys[0][0] == "alpha"
    assert keys[1][0] == "middle"
    assert keys[2][0] == "zebra"


def test_expiry(temp_db):
    """Test setting and checking expiry."""
    set_value(temp_db, "test-key", "test-value")
    set_expiry(temp_db, "test-key", -1)

    value, is_expired = get_value(temp_db, "test-key")
    assert value == "test-value"
    assert is_expired


def test_delete_key(temp_db):
    """Test deleting keys."""
    set_value(temp_db, "test-key", "test-value")
    assert delete_key(temp_db, "test-key")

    value, _ = get_value(temp_db, "test-key")
    assert value is None

    assert not delete_key(temp_db, "nonexistent")


def test_clean_expired(temp_db):
    """Test cleaning expired entries."""
    set_value(temp_db, "expired1", "value1")
    set_value(temp_db, "expired2", "value2")
    set_value(temp_db, "active", "value3")

    set_expiry(temp_db, "expired1", -1)
    set_expiry(temp_db, "expired2", -1)
    set_expiry(temp_db, "active", 3600)

    count = clean_expired(temp_db)
    assert count == 2

    keys = list_keys(temp_db)
    assert len(keys) == 1
    assert keys[0][0] == "active"


def test_db_permissions():
    """Test that new database has correct permissions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = init_db(db_path)
        conn.close()

        import stat

        mode = db_path.stat().st_mode
        assert stat.S_IMODE(mode) == 0o600
