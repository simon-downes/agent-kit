"""Tests for agent_kit.tasks.cli."""

from unittest.mock import patch

import pytest

from agent_kit.cli import main
from agent_kit.tasks.client import TaskClient


@pytest.fixture
def tmp_client(tmp_path):
    """TaskClient backed by a temp database."""
    return TaskClient(db_path=tmp_path / "tasks.db")


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
