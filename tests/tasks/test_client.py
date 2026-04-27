"""Tests for agent_kit.tasks.client."""

import pytest

from agent_kit.tasks.client import TaskClient


@pytest.fixture
def client(tmp_path):
    """TaskClient backed by a temp database."""
    return TaskClient(db_path=tmp_path / "tasks.db")


class TestCreate:
    def test_creates_pending_task(self, client):
        task = client.create("test-task", "echo", ["hello"])
        assert task["name"] == "test-task"
        assert task["status"] == "pending"
        assert task["command"] == "echo"
        assert task["args"] == ["hello"]
        assert task["created_at"] is not None
        assert task["started_at"] is None
        assert task["exit_code"] is None

    def test_returns_integer_id(self, client):
        task = client.create("test-task", "echo", [])
        assert isinstance(task["id"], int)

    def test_increments_ids(self, client):
        t1 = client.create("task-1", "echo", [])
        t2 = client.create("task-2", "echo", [])
        assert t2["id"] > t1["id"]

    def test_rejects_duplicate_active_name(self, client):
        client.create("dup-task", "echo", [])
        with pytest.raises(ValueError, match="already pending or running"):
            client.create("dup-task", "echo", [])

    def test_allows_same_name_after_completion(self, client):
        task = client.create("reuse-task", "echo", [])
        # Simulate completion
        client._conn.execute(
            "UPDATE tasks SET status = 'done' WHERE id = ?", (task["id"],)
        )
        client._conn.commit()
        task2 = client.create("reuse-task", "echo", [])
        assert task2["id"] != task["id"]

    def test_stores_args_as_list(self, client):
        task = client.create("args-task", "ls", ["-la", "/tmp"])
        assert task["args"] == ["-la", "/tmp"]

    def test_empty_args(self, client):
        task = client.create("no-args", "pwd", [])
        assert task["args"] == []
