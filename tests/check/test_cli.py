"""Tests for check CLI."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from agent_kit.check.cli import main


def test_help():
    """Test help command."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Check" in result.output


def test_no_config_file():
    """Test when config file doesn't exist."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.check.cli as cli_module

            original_get_config_path = cli_module.get_config_path
            cli_module.get_config_path = lambda: Path(tmpdir) / "tools.yaml"

            try:
                result = runner.invoke(main, [])
                assert result.exit_code == 0
                assert "No tools configured" in result.output
            finally:
                cli_module.get_config_path = original_get_config_path


def test_check_existing_tool():
    """Test checking a tool that exists."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "tools.yaml"
        config_path.write_text("""
tools:
  python:
    version_cmd: python3 --version
    version_pattern: "Python (\\\\S+)"
""")

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.check.cli as cli_module

            original_get_config_path = cli_module.get_config_path
            cli_module.get_config_path = lambda: config_path

            try:
                result = runner.invoke(main, [])
                assert result.exit_code == 0
                assert "python" in result.output
            finally:
                cli_module.get_config_path = original_get_config_path


def test_check_nonexistent_tool():
    """Test checking a tool that doesn't exist."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "tools.yaml"
        config_path.write_text("""
tools:
  notreal:
    version_cmd: notreal --version
    version_pattern: "v(\\\\S+)"
""")

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.check.cli as cli_module

            original_get_config_path = cli_module.get_config_path
            cli_module.get_config_path = lambda: config_path

            try:
                result = runner.invoke(main, [])
                assert result.exit_code == 2  # Missing tool
                assert "notreal" in result.output
                assert "-" in result.output
            finally:
                cli_module.get_config_path = original_get_config_path


def test_check_specific_tools():
    """Test checking specific tools."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "tools.yaml"
        config_path.write_text("""
tools:
  python:
    version_cmd: python3 --version
    version_pattern: "Python (\\\\S+)"
  notreal:
    version_cmd: notreal --version
    version_pattern: "v(\\\\S+)"
""")

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.check.cli as cli_module

            original_get_config_path = cli_module.get_config_path
            cli_module.get_config_path = lambda: config_path

            try:
                result = runner.invoke(main, ["python"])
                assert result.exit_code == 0
                assert "python" in result.output
                assert "notreal" not in result.output
            finally:
                cli_module.get_config_path = original_get_config_path


def test_check_unknown_tool():
    """Test checking a tool not in config."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "tools.yaml"
        config_path.write_text("""
tools:
  python:
    version_cmd: python3 --version
    version_pattern: "Python (\\\\S+)"
""")

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.check.cli as cli_module

            original_get_config_path = cli_module.get_config_path
            cli_module.get_config_path = lambda: config_path

            try:
                result = runner.invoke(main, ["unknown"])
                assert result.exit_code == 0
                assert "unknown tool" in result.output
            finally:
                cli_module.get_config_path = original_get_config_path


def test_check_with_auth():
    """Test checking tool with auth command."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "tools.yaml"
        config_path.write_text("""
tools:
  python:
    version_cmd: python3 --version
    version_pattern: "Python (\\\\S+)"
    auth_cmd: python3 -c "print('authenticated')"
""")

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.check.cli as cli_module

            original_get_config_path = cli_module.get_config_path
            cli_module.get_config_path = lambda: config_path

            try:
                result = runner.invoke(main, [])
                assert result.exit_code == 0
                assert "python" in result.output
            finally:
                cli_module.get_config_path = original_get_config_path


def test_verbose_output():
    """Test verbose output."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "tools.yaml"
        config_path.write_text("""
tools:
  python:
    version_cmd: python3 --version
    version_pattern: "Python (\\\\S+)"
    auth_cmd: python3 -c "print('test output')"
""")

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.check.cli as cli_module

            original_get_config_path = cli_module.get_config_path
            cli_module.get_config_path = lambda: config_path

            try:
                result = runner.invoke(main, ["-v"])
                assert result.exit_code == 0
                assert "python" in result.output
                assert "Exit code" in result.output
                assert "Version:" in result.output
                assert "Found" not in result.output  # Should not show "Found"
            finally:
                cli_module.get_config_path = original_get_config_path


def test_auth_failure_exit_code():
    """Test exit code when auth fails."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "tools.yaml"
        config_path.write_text("""
tools:
  python:
    version_cmd: python3 --version
    version_pattern: "Python (\\\\S+)"
    auth_cmd: python3 -c "import sys; sys.exit(1)"
""")

        with runner.isolated_filesystem(temp_dir=tmpdir):
            import agent_kit.check.cli as cli_module

            original_get_config_path = cli_module.get_config_path
            cli_module.get_config_path = lambda: config_path

            try:
                result = runner.invoke(main, [])
                assert result.exit_code == 1  # Auth failure
            finally:
                cli_module.get_config_path = original_get_config_path
