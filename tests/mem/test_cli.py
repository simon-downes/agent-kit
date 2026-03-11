"""Tests for mem CLI."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from agent_kit.mem.cli import main


def test_help():
    """Test help command."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Mem - Agent memory storage and retrieval" in result.output


def test_add_memory():
    """Test adding a memory."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.mem.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                result = runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "decision", "Test decision"],
                )
                assert result.exit_code == 0
                assert "Added memory 1" in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_add_memory_with_all_options():
    """Test adding a memory with all optional fields."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.mem.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                result = runner.invoke(
                    main,
                    [
                        "add",
                        "--project",
                        "test-project",
                        "--kind",
                        "change",
                        "--topic",
                        "api-design",
                        "--ref",
                        "abc123",
                        "--metadata",
                        '{"key": "value"}',
                        "Test change",
                    ],
                )
                assert result.exit_code == 0
                assert "Added memory 1" in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_add_memory_from_stdin():
    """Test adding a memory from stdin."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.mem.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                result = runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "note", "-"],
                    input="Multi-line\nsummary from\nstdin",
                )
                assert result.exit_code == 0
                assert "Added memory 1" in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_add_memory_invalid_project():
    """Test adding a memory with invalid project name."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["add", "--project", "INVALID_PROJECT", "--kind", "decision", "Test"],
    )
    assert result.exit_code == 1
    assert "lower-kebab-case" in result.output


def test_add_memory_invalid_kind():
    """Test adding a memory with invalid kind."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["add", "--project", "test-project", "--kind", "invalid", "Test"],
    )
    assert result.exit_code == 1
    assert "Invalid kind" in result.output


def test_list_memories():
    """Test listing memories."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.mem.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                # Add some memories
                runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "decision", "First decision"],
                )
                runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "change", "First change"],
                )

                # List all
                result = runner.invoke(main, ["list", "--project", "test-project"])
                assert result.exit_code == 0
                assert "decision" in result.output
                assert "change" in result.output
                assert "First decision" in result.output
                assert "First change" in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_list_memories_json():
    """Test listing memories in JSON format."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.mem.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "decision", "Test decision"],
                )

                result = runner.invoke(main, ["list", "--project", "test-project", "--json"])
                assert result.exit_code == 0
                assert '"project": "test-project"' in result.output
                assert '"kind": "decision"' in result.output
                assert '"summary": "Test decision"' in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_list_memories_with_filters():
    """Test listing memories with filters."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.mem.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "decision", "Decision 1"],
                )
                runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "change", "Change 1"],
                )

                result = runner.invoke(
                    main, ["list", "--project", "test-project", "--kind", "decision"]
                )
                assert result.exit_code == 0
                assert "Decision 1" in result.output
                assert "Change 1" not in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_stats():
    """Test stats command."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.mem.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "decision", "Decision 1"],
                )
                runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "decision", "Decision 2"],
                )
                runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "change", "Change 1"],
                )

                result = runner.invoke(main, ["stats", "--project", "test-project"])
                assert result.exit_code == 0
                assert "Total memories: 3" in result.output
                assert "decision" in result.output
                assert "change" in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_stats_empty_project():
    """Test stats for project with no memories."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.mem.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                result = runner.invoke(main, ["stats", "--project", "nonexistent-project"])
                assert result.exit_code == 0
                assert "No memories found" in result.output
            finally:
                db_module.get_db_path = original_get_db_path
