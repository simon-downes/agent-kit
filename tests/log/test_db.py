"""Tests for log database operations."""

import tempfile
from pathlib import Path

import pytest

from agent_kit.log import db


@pytest.fixture
def temp_db(monkeypatch):
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setattr("agent_kit.log.db.get_db_path", lambda: db_path)
        yield db_path


def test_database_initialization(temp_db):
    """Test that database is created with correct schema."""
    conn = db.get_connection()
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert "entries" in tables

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = [row[0] for row in cursor.fetchall()]
    assert "idx_project_ts" in indexes
    assert "idx_project_kind" in indexes
    assert "idx_project_topic" in indexes
    assert "idx_ts" in indexes
    conn.close()


def test_add_entry(temp_db):
    """Test adding an entry."""
    entry_id = db.add_entry(
        project="test-project",
        kind="decision",
        summary="Test decision",
    )
    assert entry_id == 1


def test_add_entry_with_all_fields(temp_db):
    """Test adding an entry with all optional fields."""
    entry_id = db.add_entry(
        project="test-project",
        kind="change",
        summary="Test change",
        topic="api-design",
        ref="abc123",
        metadata='{"key": "value"}',
    )
    assert entry_id == 1

    entries = db.list_entries(project="test-project")
    assert len(entries) == 1
    assert entries[0]["topic"] == "api-design"
    assert entries[0]["ref"] == "abc123"
    assert entries[0]["metadata"] == '{"key": "value"}'


def test_list_entries_empty(temp_db):
    """Test listing entries for project with no entries."""
    entries = db.list_entries(project="nonexistent-project")
    assert len(entries) == 0


def test_list_entries_ordered_by_time(temp_db):
    """Test that entries are returned in reverse chronological order."""
    import time

    db.add_entry("test-project", "decision", "First")
    time.sleep(1.1)
    db.add_entry("test-project", "change", "Second")
    time.sleep(1.1)
    db.add_entry("test-project", "issue", "Third")

    entries = db.list_entries(project="test-project")
    assert len(entries) == 3
    assert entries[0]["summary"] == "Third"
    assert entries[1]["summary"] == "Second"
    assert entries[2]["summary"] == "First"


def test_list_entries_with_limit(temp_db):
    """Test limiting number of results."""
    for i in range(10):
        db.add_entry("test-project", "note", f"Entry {i}")

    entries = db.list_entries(project="test-project", limit=5)
    assert len(entries) == 5


def test_list_entries_filter_by_kind(temp_db):
    """Test filtering entries by kind."""
    db.add_entry("test-project", "decision", "Decision 1")
    db.add_entry("test-project", "change", "Change 1")
    db.add_entry("test-project", "decision", "Decision 2")

    entries = db.list_entries(project="test-project", kind="decision")
    assert len(entries) == 2
    assert all(e["kind"] == "decision" for e in entries)


def test_list_entries_filter_by_topic(temp_db):
    """Test filtering entries by topic."""
    db.add_entry("test-project", "decision", "Decision 1", topic="api-design")
    db.add_entry("test-project", "change", "Change 1", topic="database")
    db.add_entry("test-project", "decision", "Decision 2", topic="api-design")

    entries = db.list_entries(project="test-project", topic="api-design")
    assert len(entries) == 2
    assert all(e["topic"] == "api-design" for e in entries)


def test_list_entries_cross_project(temp_db):
    """Test listing entries across all projects."""
    db.add_entry("project-a", "decision", "Project A entry")
    db.add_entry("project-b", "decision", "Project B entry")

    entries = db.list_entries()
    assert len(entries) == 2


def test_list_entries_with_since(temp_db):
    """Test filtering entries with --since."""
    db.add_entry("test-project", "decision", "Recent entry")

    # Future date should return nothing
    entries = db.list_entries(project="test-project", since="2099-01-01")
    assert len(entries) == 0

    # Past date should return the entry
    entries = db.list_entries(project="test-project", since="2020-01-01")
    assert len(entries) == 1


def test_list_entries_with_until(temp_db):
    """Test filtering entries with --until."""
    db.add_entry("test-project", "decision", "Entry")

    # Past date should return nothing
    entries = db.list_entries(project="test-project", until="2020-01-01")
    assert len(entries) == 0

    # Future date should return the entry
    entries = db.list_entries(project="test-project", until="2099-01-01")
    assert len(entries) == 1


def test_parse_relative_date():
    """Test relative date parsing."""
    result = db.parse_date_filter("7d")
    assert len(result) == 10  # YYYY-MM-DD format

    result = db.parse_date_filter("4w")
    assert len(result) == 10

    result = db.parse_date_filter("2025-06-15")
    assert result == "2025-06-15"


def test_parse_relative_date_invalid():
    """Test invalid relative date formats."""
    with pytest.raises(ValueError, match="Invalid relative date"):
        db.parse_date_filter("7m")

    with pytest.raises(ValueError, match="Invalid relative date"):
        db.parse_date_filter("abc")


def test_get_stats_empty(temp_db):
    """Test stats for project with no entries."""
    stats = db.get_stats(project="nonexistent-project")
    assert stats["by_kind"] == {}
    assert stats["activity"]["total"] == 0
    assert stats["activity"]["last_7_days"] == 0
    assert stats["activity"]["last_30_days"] == 0


def test_get_stats_with_data(temp_db):
    """Test stats with actual data."""
    db.add_entry("test-project", "decision", "Decision 1")
    db.add_entry("test-project", "decision", "Decision 2")
    db.add_entry("test-project", "change", "Change 1")
    db.add_entry("test-project", "issue", "Issue 1")

    stats = db.get_stats(project="test-project")
    assert stats["by_kind"]["decision"] == 2
    assert stats["by_kind"]["change"] == 1
    assert stats["by_kind"]["issue"] == 1
    assert stats["activity"]["total"] == 4
    assert stats["activity"]["last_7_days"] == 4
    assert stats["activity"]["last_30_days"] == 4


def test_get_stats_cross_project(temp_db):
    """Test cross-project stats."""
    db.add_entry("project-a", "decision", "A entry")
    db.add_entry("project-b", "change", "B entry")
    db.add_entry("project-b", "note", "B note")

    stats = db.get_stats()
    assert stats["activity"]["total"] == 3
    assert stats["by_project"]["project-a"] == 1
    assert stats["by_project"]["project-b"] == 2


def test_multiple_projects(temp_db):
    """Test that projects are isolated when filtered."""
    db.add_entry("project-a", "decision", "Project A entry")
    db.add_entry("project-b", "decision", "Project B entry")

    entries_a = db.list_entries(project="project-a")
    entries_b = db.list_entries(project="project-b")

    assert len(entries_a) == 1
    assert len(entries_b) == 1
    assert entries_a[0]["summary"] == "Project A entry"
    assert entries_b[0]["summary"] == "Project B entry"
