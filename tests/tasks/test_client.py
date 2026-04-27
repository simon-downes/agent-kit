"""Tests for agent_kit.tasks.client."""

import time
from datetime import UTC, datetime, timedelta

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


class TestRun:
    def test_claims_and_executes_pending(self, client):
        client.create("t1", "echo", ["hello"])
        results = client.run()
        assert len(results) == 1
        assert results[0]["status"] == "done"
        assert results[0]["exit_code"] == 0

    def test_no_pending_returns_empty(self, client):
        assert client.run() == []

    def test_creates_log_files(self, client):
        task = client.create("t1", "echo", ["hello"])
        client.run()
        log = client._log_dir / f"t1-{task['id']}.log"
        err_log = client._log_dir / f"t1-{task['id']}.error.log"
        assert log.exists()
        assert err_log.exists()
        assert "hello" in log.read_text()

    def test_captures_exit_code_on_failure(self, client):
        client.create("t1", "sh", ["-c", "exit 42"])
        results = client.run()
        assert results[0]["status"] == "failed"
        assert results[0]["exit_code"] == 42
        assert results[0]["error"] == "exit code 42"

    def test_handles_command_not_found(self, client):
        client.create("t1", "/nonexistent/binary", [])
        results = client.run()
        assert results[0]["status"] == "failed"
        assert results[0]["error"] is not None

    def test_parallel_execution(self, client, monkeypatch):
        """Multiple tasks run in parallel, not sequentially."""
        monkeypatch.setattr("agent_kit.tasks.client._POLL_INTERVAL", 0.05)
        client.create("t1", "sleep", ["0.1"])
        client.create("t2", "sleep", ["0.1"])
        start = time.time()
        results = client.run()
        elapsed = time.time() - start
        assert len(results) == 2
        assert all(r["status"] == "done" for r in results)
        # If sequential, would take ~0.2s. Parallel should be ~0.1s.
        assert elapsed < 0.5

    def test_timeout_kills_task(self, client, monkeypatch):
        """Task killed when log file is stale beyond timeout."""
        monkeypatch.setattr("agent_kit.tasks.client._POLL_INTERVAL", 0.1)
        monkeypatch.setattr("agent_kit.tasks.client._TERM_GRACE_PERIOD", 1)
        # Use a very short timeout
        monkeypatch.setattr(
            "agent_kit.tasks.client.load_config",
            lambda: {"tasks": {"inactivity_timeout": 0}},
        )
        client.create("t1", "sleep", ["60"])
        results = client.run()
        assert results[0]["status"] == "timeout"

    def test_orphan_detection(self, client, monkeypatch):
        """Running tasks with stale logs are marked as timed out."""
        monkeypatch.setattr(
            "agent_kit.tasks.client.load_config",
            lambda: {"tasks": {"inactivity_timeout": 0}},
        )
        # Create a task and manually set it to running with a stale log
        task = client.create("orphan", "echo", [])
        client._conn.execute(
            "UPDATE tasks SET status = 'running', started_at = ? WHERE id = ?",
            ("2020-01-01T00:00:00+00:00", task["id"]),
        )
        client._conn.commit()
        # Run should detect the orphan and timeout it
        client.run()
        updated = client.get("orphan")
        assert updated["status"] == "timeout"

    def test_external_cancel_stops_task(self, client, monkeypatch):
        """A task cancelled externally during execution is terminated."""
        import threading

        from agent_kit.tasks.db import get_connection

        monkeypatch.setattr("agent_kit.tasks.client._POLL_INTERVAL", 0.1)
        monkeypatch.setattr("agent_kit.tasks.client._TERM_GRACE_PERIOD", 1)
        client.create("t1", "sleep", ["60"])

        def cancel_after_delay():
            time.sleep(0.3)
            conn = get_connection(client._db_path)
            conn.execute("UPDATE tasks SET status = 'cancelled' WHERE name = 't1'")
            conn.commit()

        t = threading.Thread(target=cancel_after_delay)
        t.start()
        results = client.run()
        t.join()
        assert results[0]["status"] == "cancelled"


class TestParseDuration:
    def test_days(self):
        from agent_kit.tasks.client import parse_duration

        assert parse_duration("7d") == timedelta(days=7)

    def test_hours(self):
        from agent_kit.tasks.client import parse_duration

        assert parse_duration("2h") == timedelta(hours=2)

    def test_minutes(self):
        from agent_kit.tasks.client import parse_duration

        assert parse_duration("30m") == timedelta(minutes=30)

    def test_invalid(self):
        from agent_kit.tasks.client import parse_duration

        with pytest.raises(ValueError, match="invalid duration"):
            parse_duration("abc")

    def test_no_unit(self):
        from agent_kit.tasks.client import parse_duration

        with pytest.raises(ValueError, match="invalid duration"):
            parse_duration("42")


class TestClean:
    def test_removes_old_completed_tasks(self, client):
        task = client.create("old-task", "echo", [])
        # Simulate completion 10 days ago
        client._conn.execute(
            "UPDATE tasks SET status = 'done', finished_at = '2020-01-01T00:00:00+00:00' "
            "WHERE id = ?",
            (task["id"],),
        )
        client._conn.commit()
        # Create log files
        client._log_dir.mkdir(parents=True, exist_ok=True)
        log = client._log_dir / f"old-task-{task['id']}.log"
        err_log = client._log_dir / f"old-task-{task['id']}.error.log"
        log.write_text("output")
        err_log.write_text("errors")

        count = client.clean(timedelta(days=7))
        assert count == 1
        assert not log.exists()
        assert not err_log.exists()

    def test_preserves_recent_tasks(self, client):
        task = client.create("recent-task", "echo", [])
        client._conn.execute(
            "UPDATE tasks SET status = 'done', finished_at = ? WHERE id = ?",
            (datetime.now(UTC).isoformat(), task["id"]),
        )
        client._conn.commit()
        count = client.clean(timedelta(days=7))
        assert count == 0

    def test_preserves_active_tasks(self, client):
        client.create("active-task", "echo", [])
        count = client.clean(timedelta(days=0))
        assert count == 0
