"""Tests for agent_kit.tasks.cli."""

import json
from unittest.mock import patch

import pytest

from agent_kit.cli import main
from agent_kit.tasks.client import TaskClient


@pytest.fixture
def tmp_client(tmp_path):
    """TaskClient backed by a temp database with temp log dir."""
    c = TaskClient(db_path=tmp_path / "tasks.db")
    c._log_dir = tmp_path / "logs"
    c._log_dir.mkdir()
    return c


@pytest.fixture(autouse=True)
def _use_tmp_client(tmp_client):
    """Route all CLI commands to a temp-backed TaskClient."""
    with patch("agent_kit.tasks.cli._get_client", return_value=tmp_client):
        yield


class TestCreate:
    def test_creates_task(self, cli_runner):
        result = cli_runner.invoke(main, ["tasks", "create", "--name", "t1", "--", "echo", "hi"])
        assert result.exit_code == 0
        assert result.output.strip().isdigit()

    def test_requires_name(self, cli_runner):
        result = cli_runner.invoke(main, ["tasks", "create", "--", "echo"])
        assert result.exit_code != 0

    def test_requires_command(self, cli_runner):
        result = cli_runner.invoke(main, ["tasks", "create", "--name", "t1"])
        assert result.exit_code != 0

    def test_duplicate_name_fails(self, cli_runner):
        cli_runner.invoke(main, ["tasks", "create", "--name", "dup", "--", "echo"])
        result = cli_runner.invoke(main, ["tasks", "create", "--name", "dup", "--", "echo"])
        assert result.exit_code == 1


class TestList:
    def test_default_shows_active(self, cli_runner, tmp_client):
        tmp_client.create("t1", "echo", [])
        t2 = tmp_client.create("t2", "echo", [])
        tmp_client._conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (t2["id"],))
        tmp_client._conn.commit()
        result = cli_runner.invoke(main, ["tasks", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["name"] == "t1"

    def test_show_all(self, cli_runner, tmp_client):
        tmp_client.create("t1", "echo", [])
        t2 = tmp_client.create("t2", "echo", [])
        tmp_client._conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (t2["id"],))
        tmp_client._conn.commit()
        result = cli_runner.invoke(main, ["tasks", "list", "--all"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2

    def test_filter_by_status(self, cli_runner, tmp_client):
        tmp_client.create("t1", "echo", [])
        t2 = tmp_client.create("t2", "echo", [])
        tmp_client._conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (t2["id"],))
        tmp_client._conn.commit()
        result = cli_runner.invoke(main, ["tasks", "list", "--status", "done"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["name"] == "t2"


class TestStatus:
    def test_shows_task(self, cli_runner, tmp_client):
        tmp_client.create("my-task", "echo", ["hello"])
        result = cli_runner.invoke(main, ["tasks", "status", "my-task"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "my-task"

    def test_not_found(self, cli_runner):
        result = cli_runner.invoke(main, ["tasks", "status", "nope"])
        assert result.exit_code == 1


class TestLog:
    def test_shows_log(self, cli_runner, tmp_client):
        task = tmp_client.create("my-task", "echo", [])
        log_path = tmp_client._log_dir / f"my-task-{task['id']}.log"
        log_path.write_text("hello world\n")
        result = cli_runner.invoke(main, ["tasks", "log", "my-task"])
        assert result.exit_code == 0
        assert "hello world" in result.output

    def test_shows_error_log(self, cli_runner, tmp_client):
        task = tmp_client.create("my-task", "echo", [])
        err_path = tmp_client._log_dir / f"my-task-{task['id']}.error.log"
        err_path.write_text("something failed\n")
        result = cli_runner.invoke(main, ["tasks", "log", "my-task", "--error"])
        assert result.exit_code == 0
        assert "something failed" in result.output

    def test_missing_log(self, cli_runner, tmp_client):
        tmp_client.create("my-task", "echo", [])
        result = cli_runner.invoke(main, ["tasks", "log", "my-task"])
        assert result.exit_code == 1


class TestCancel:
    def test_cancel_pending(self, cli_runner, tmp_client):
        tmp_client.create("my-task", "echo", [])
        result = cli_runner.invoke(main, ["tasks", "cancel", "my-task"])
        assert result.exit_code == 0
        assert "Cancelled" in result.output

    def test_cancel_completed_fails(self, cli_runner, tmp_client):
        task = tmp_client.create("my-task", "echo", [])
        tmp_client._conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (task["id"],))
        tmp_client._conn.commit()
        result = cli_runner.invoke(main, ["tasks", "cancel", "my-task"])
        assert result.exit_code == 1


class TestRun:
    def test_executes_pending(self, cli_runner, tmp_client):
        tmp_client.create("t1", "echo", ["hello"])
        result = cli_runner.invoke(main, ["tasks", "run"])
        assert result.exit_code == 0
        task = tmp_client.get("t1")
        assert task["status"] == "done"

    def test_no_pending(self, cli_runner):
        result = cli_runner.invoke(main, ["tasks", "run"])
        assert result.exit_code == 0
