"""Tests for kv CLI."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from agent_kit.kv.cli import main


def test_help():
    """Test help command."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "KV - A simple key-value store" in result.output


def test_set_and_get():
    """Test set and get commands."""
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        env = {"KV_DB": db_path}

        result = runner.invoke(main, ["set", "test-key", "test-value"], env=env)
        assert result.exit_code == 0

        result = runner.invoke(main, ["get", "test-key"], env=env)
        assert result.exit_code == 0
        assert result.output.strip() == "test-value"
    finally:
        Path(db_path).unlink()


def test_get_nonexistent():
    """Test getting nonexistent key."""
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        env = {"KV_DB": db_path}
        result = runner.invoke(main, ["get", "nonexistent"], env=env)
        assert result.exit_code == 2
    finally:
        Path(db_path).unlink()


def test_invalid_key():
    """Test setting invalid key."""
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        env = {"KV_DB": db_path}
        result = runner.invoke(main, ["set", "INVALID", "value"], env=env)
        assert result.exit_code == 1
        assert "Invalid key" in result.output
    finally:
        Path(db_path).unlink()


def test_stdin_input():
    """Test setting value from stdin."""
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        env = {"KV_DB": db_path}
        result = runner.invoke(main, ["set", "test-key"], input="from stdin", env=env)
        assert result.exit_code == 0

        result = runner.invoke(main, ["get", "test-key"], env=env)
        assert result.output.strip() == "from stdin"
    finally:
        Path(db_path).unlink()


def test_list_plain():
    """Test list command with plain output."""
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        env = {"KV_DB": db_path}
        runner.invoke(main, ["set", "alpha", "first"], env=env)
        runner.invoke(main, ["set", "zebra", "last"], env=env)

        result = runner.invoke(main, ["list", "--plain"], env=env)
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        assert lines[0].startswith("alpha\t")
        assert lines[1].startswith("zebra\t")
    finally:
        Path(db_path).unlink()


def test_rm():
    """Test rm command."""
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        env = {"KV_DB": db_path}
        runner.invoke(main, ["set", "test-key", "value"], env=env)

        result = runner.invoke(main, ["rm", "test-key"], env=env)
        assert result.exit_code == 0

        result = runner.invoke(main, ["get", "test-key"], env=env)
        assert result.exit_code == 2
    finally:
        Path(db_path).unlink()
