"""Tests for mem database operations."""

import tempfile
from pathlib import Path

import pytest

from agent_kit.mem import db


@pytest.fixture
def temp_db(monkeypatch):
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setattr("agent_kit.mem.db.get_db_path", lambda: db_path)
        yield db_path


def test_database_initialization(temp_db):
    """Test that database is created with correct schema."""
    conn = db.get_connection()
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert "memories" in tables

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = [row[0] for row in cursor.fetchall()]
    assert "idx_project_ts" in indexes
    assert "idx_project_kind" in indexes
    assert "idx_project_topic" in indexes
    conn.close()


def test_add_memory(temp_db):
    """Test adding a memory."""
    memory_id = db.add_memory(
        project="test-project",
        kind="decision",
        summary="Test decision",
    )
    assert memory_id == 1


def test_add_memory_with_all_fields(temp_db):
    """Test adding a memory with all optional fields."""
    memory_id = db.add_memory(
        project="test-project",
        kind="change",
        summary="Test change",
        topic="api-design",
        ref="abc123",
        metadata='{"key": "value"}',
    )
    assert memory_id == 1

    memories = db.list_memories("test-project")
    assert len(memories) == 1
    assert memories[0]["topic"] == "api-design"
    assert memories[0]["ref"] == "abc123"
    assert memories[0]["metadata"] == '{"key": "value"}'


def test_list_memories_empty(temp_db):
    """Test listing memories for project with no memories."""
    memories = db.list_memories("nonexistent-project")
    assert len(memories) == 0


def test_list_memories_ordered_by_time(temp_db):
    """Test that memories are returned in reverse chronological order."""
    import time

    db.add_memory("test-project", "decision", "First")
    time.sleep(1.1)  # SQLite CURRENT_TIMESTAMP has second precision
    db.add_memory("test-project", "change", "Second")
    time.sleep(1.1)
    db.add_memory("test-project", "issue", "Third")

    memories = db.list_memories("test-project")
    assert len(memories) == 3
    # Most recent first
    assert memories[0]["summary"] == "Third"
    assert memories[1]["summary"] == "Second"
    assert memories[2]["summary"] == "First"


def test_list_memories_with_limit(temp_db):
    """Test limiting number of results."""
    for i in range(10):
        db.add_memory("test-project", "note", f"Memory {i}")

    memories = db.list_memories("test-project", limit=5)
    assert len(memories) == 5


def test_list_memories_filter_by_kind(temp_db):
    """Test filtering memories by kind."""
    db.add_memory("test-project", "decision", "Decision 1")
    db.add_memory("test-project", "change", "Change 1")
    db.add_memory("test-project", "decision", "Decision 2")

    memories = db.list_memories("test-project", kind="decision")
    assert len(memories) == 2
    assert all(m["kind"] == "decision" for m in memories)


def test_list_memories_filter_by_topic(temp_db):
    """Test filtering memories by topic."""
    db.add_memory("test-project", "decision", "Decision 1", topic="api-design")
    db.add_memory("test-project", "change", "Change 1", topic="database")
    db.add_memory("test-project", "decision", "Decision 2", topic="api-design")

    memories = db.list_memories("test-project", topic="api-design")
    assert len(memories) == 2
    assert all(m["topic"] == "api-design" for m in memories)


def test_get_stats_empty(temp_db):
    """Test stats for project with no memories."""
    stats = db.get_stats("nonexistent-project")
    assert stats["by_kind"] == {}
    assert stats["activity"]["total"] == 0
    assert stats["activity"]["last_7_days"] == 0
    assert stats["activity"]["last_30_days"] == 0


def test_get_stats_with_data(temp_db):
    """Test stats with actual data."""
    db.add_memory("test-project", "decision", "Decision 1")
    db.add_memory("test-project", "decision", "Decision 2")
    db.add_memory("test-project", "change", "Change 1")
    db.add_memory("test-project", "issue", "Issue 1")

    stats = db.get_stats("test-project")
    assert stats["by_kind"]["decision"] == 2
    assert stats["by_kind"]["change"] == 1
    assert stats["by_kind"]["issue"] == 1
    assert stats["activity"]["total"] == 4
    assert stats["activity"]["last_7_days"] == 4
    assert stats["activity"]["last_30_days"] == 4


def test_multiple_projects(temp_db):
    """Test that projects are isolated."""
    db.add_memory("project-a", "decision", "Project A memory")
    db.add_memory("project-b", "decision", "Project B memory")

    memories_a = db.list_memories("project-a")
    memories_b = db.list_memories("project-b")

    assert len(memories_a) == 1
    assert len(memories_b) == 1
    assert memories_a[0]["summary"] == "Project A memory"
    assert memories_b[0]["summary"] == "Project B memory"
