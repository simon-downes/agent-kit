"""Tests for log CLI."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from agent_kit.log.cli import main


def test_help():
    """Test help command."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Log - Activity log for development workflows" in result.output


def test_add_entry():
    """Test adding an entry."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.log.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                result = runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "decision", "Test decision"],
                )
                assert result.exit_code == 0
                assert "Added entry 1" in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_add_entry_with_all_options():
    """Test adding an entry with all optional fields."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.log.db as db_module

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
                assert "Added entry 1" in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_add_entry_from_stdin():
    """Test adding an entry from stdin."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.log.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                result = runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "note", "-"],
                    input="Multi-line\nsummary from\nstdin",
                )
                assert result.exit_code == 0
                assert "Added entry 1" in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_add_entry_invalid_project():
    """Test adding an entry with invalid project name."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["add", "--project", "INVALID_PROJECT", "--kind", "decision", "Test"],
    )
    assert result.exit_code == 1
    assert "lower-kebab-case" in result.output


def test_add_entry_invalid_kind():
    """Test adding an entry with invalid kind."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["add", "--project", "test-project", "--kind", "invalid", "Test"],
    )
    assert result.exit_code == 1
    assert "Invalid kind" in result.output


def test_add_entry_dropped_kind():
    """Test that dropped kinds are rejected."""
    runner = CliRunner()
    for kind in ["context", "pattern", "dependency", "experiment"]:
        result = runner.invoke(
            main,
            ["add", "--project", "test-project", "--kind", kind, "Test"],
        )
        assert result.exit_code == 1
        assert "Invalid kind" in result.output


def test_add_entry_new_kind():
    """Test that the new 'request' kind works."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.log.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                result = runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "request", "Add auth endpoint"],
                )
                assert result.exit_code == 0
                assert "Added entry 1" in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_list_entries():
    """Test listing entries."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.log.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "decision", "First decision"],
                )
                runner.invoke(
                    main,
                    ["add", "--project", "test-project", "--kind", "change", "First change"],
                )

                result = runner.invoke(main, ["list", "--project", "test-project"])
                assert result.exit_code == 0
                assert "decision" in result.output
                assert "change" in result.output
                assert "First decision" in result.output
                assert "First change" in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_list_entries_cross_project():
    """Test listing entries across all projects."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.log.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                runner.invoke(
                    main,
                    ["add", "--project", "project-a", "--kind", "decision", "A decision"],
                )
                runner.invoke(
                    main,
                    ["add", "--project", "project-b", "--kind", "change", "B change"],
                )

                result = runner.invoke(main, ["list"])
                assert result.exit_code == 0
                assert "A decision" in result.output
                assert "B change" in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_list_entries_json():
    """Test listing entries in JSON format."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.log.db as db_module

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


def test_list_entries_with_filters():
    """Test listing entries with filters."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.log.db as db_module

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
            import agent_kit.log.db as db_module

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
                assert "Total entries: 3" in result.output
                assert "decision" in result.output
                assert "change" in result.output
            finally:
                db_module.get_db_path = original_get_db_path


def test_stats_empty_project():
    """Test stats for project with no entries."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.log.db as db_module

            original_get_db_path = db_module.get_db_path
            db_module.get_db_path = lambda: db_path

            try:
                result = runner.invoke(main, ["stats", "--project", "nonexistent-project"])
                assert result.exit_code == 0
                assert "No entries found" in result.output
            finally:
                db_module.get_db_path = original_get_db_path
