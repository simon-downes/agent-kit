"""Tests for agent_kit.tasks.client."""

import pytest

from agent_kit.tasks.client import TaskClient


@pytest.fixture
def client(tmp_path):
    """TaskClient backed by a temp database."""
    c = TaskClient(db_path=tmp_path / "tasks.db")
    c._log_dir = tmp_path / "logs"
    c._log_dir.mkdir()
    return c


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


class TestListTasks:
    def test_default_shows_pending_and_running(self, client):
        client.create("t1", "echo", [])
        t2 = client.create("t2", "echo", [])
        client._conn.execute("UPDATE tasks SET status = 'running' WHERE id = ?", (t2["id"],))
        t3 = client.create("t3", "echo", [])
        client._conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (t3["id"],))
        client._conn.commit()
        result = client.list_tasks()
        names = [t["name"] for t in result]
        assert "t1" in names
        assert "t2" in names
        assert "t3" not in names

    def test_show_all(self, client):
        client.create("t1", "echo", [])
        t2 = client.create("t2", "echo", [])
        client._conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (t2["id"],))
        client._conn.commit()
        result = client.list_tasks(show_all=True)
        assert len(result) == 2

    def test_filter_by_status(self, client):
        client.create("t1", "echo", [])
        t2 = client.create("t2", "echo", [])
        client._conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (t2["id"],))
        client._conn.commit()
        result = client.list_tasks(status="done")
        assert len(result) == 1
        assert result[0]["name"] == "t2"

    def test_ordered_ascending(self, client):
        client.create("first", "echo", [])
        client.create("second", "echo", [])
        result = client.list_tasks()
        assert result[0]["name"] == "first"
        assert result[1]["name"] == "second"

    def test_limit(self, client):
        for i in range(5):
            client.create(f"t{i}", "echo", [])
        result = client.list_tasks(limit=3)
        assert len(result) == 3


class TestGet:
    def test_get_by_name(self, client):
        client.create("my-task", "echo", [])
        task = client.get("my-task")
        assert task["name"] == "my-task"

    def test_get_by_id(self, client):
        created = client.create("my-task", "echo", [])
        task = client.get(str(created["id"]))
        assert task["name"] == "my-task"

    def test_name_takes_precedence(self, client):
        created = client.create("my-task", "echo", [])
        task = client.get("my-task")
        assert task["id"] == created["id"]

    def test_not_found(self, client):
        with pytest.raises(ValueError, match="not found"):
            client.get("nonexistent")

    def test_not_found_numeric(self, client):
        with pytest.raises(ValueError, match="not found"):
            client.get("99999")


class TestGetLogPath:
    def test_stdout_log_path(self, client):
        client.create("my-task", "echo", [])
        path = client.get_log_path("my-task")
        assert path.name.startswith("my-task-")
        assert path.suffix == ".log"

    def test_error_log_path(self, client):
        client.create("my-task", "echo", [])
        path = client.get_log_path("my-task", error=True)
        assert "my-task-" in path.name
        assert path.name.endswith(".error.log")


class TestCancel:
    def test_cancel_pending(self, client):
        client.create("my-task", "echo", [])
        task = client.cancel("my-task")
        assert task["status"] == "cancelled"
        assert task["finished_at"] is not None
        assert task["error"] is None

    def test_cancel_running(self, client):
        created = client.create("my-task", "echo", [])
        client._conn.execute("UPDATE tasks SET status = 'running' WHERE id = ?", (created["id"],))
        client._conn.commit()
        task = client.cancel("my-task")
        assert task["status"] == "cancelled"
        assert task["error"] == "cancelled by user"

    def test_cancel_completed_raises(self, client):
        created = client.create("my-task", "echo", [])
        client._conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (created["id"],))
        client._conn.commit()
        with pytest.raises(ValueError, match="already completed"):
            client.cancel("my-task")
