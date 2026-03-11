# Contributing to Agent Kit

Guidelines for developing new tools and maintaining the codebase.

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager

## Setup

```bash
# Clone repository
git clone https://github.com/simon-downes/agent-kit.git
cd agent-kit

# Sync dependencies (including dev dependencies)
uv sync

# Install as editable tool for testing
uv tool install --editable .
```

## Project Structure

```
agent-kit/
├── pyproject.toml              # Package configuration
├── src/agent_kit/
│   ├── cli.py                  # Main CLI entry point
│   ├── kv/                     # Key-value store tool
│   │   ├── __init__.py
│   │   ├── cli.py              # Click commands
│   │   └── db.py               # Database operations
│   ├── mem/                    # Agent memory tool
│   │   ├── __init__.py
│   │   ├── cli.py              # Click commands
│   │   ├── db.py               # Database operations
│   │   ├── models.py           # Data models and validation
│   │   └── formatters.py       # Output formatting
│   ├── oauth/                  # OAuth authentication
│   └── notion/                 # Notion integration
└── tests/
    ├── kv/
    │   ├── test_cli.py
    │   └── test_db.py
    ├── mem/
    │   ├── test_cli.py
    │   ├── test_db.py
    │   └── test_models.py
    └── ...
```

## Adding a New Tool

### 1. Create Module Structure

```bash
mkdir -p src/agent_kit/newtool
touch src/agent_kit/newtool/__init__.py
touch src/agent_kit/newtool/cli.py
```

### 2. Implement CLI Commands

Use Click for command-line interface:

```python
# src/agent_kit/newtool/cli.py
import click
from rich.console import Console

console = Console()

@click.group()
def main() -> None:
    """NewTool - Brief description."""
    pass

@main.command("subcommand")
@click.argument("required_arg")
@click.option("--optional", help="Optional parameter")
def subcommand(required_arg: str, optional: str | None) -> None:
    """Subcommand description."""
    try:
        # Implementation
        console.print("[green]Success![/green]")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
```

### 3. Register Command

Add to `src/agent_kit/cli.py`:

```python
from agent_kit.newtool.cli import main as newtool_cli

main.add_command(newtool_cli, name="newtool")
```

### 4. Add Tests

Create test files in `tests/newtool/`:

```python
# tests/newtool/test_cli.py
from click.testing import CliRunner
from agent_kit.newtool.cli import main

def test_help():
    """Test help command."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "NewTool" in result.output
```

## Common Patterns

### Database Storage

Use SQLite for persistent storage:

```python
import sqlite3
from pathlib import Path

def get_db_path() -> Path:
    """Get database file path."""
    db_dir = Path.home() / ".agent-kit" / "newtool"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "db"

def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    db_path = get_db_path()
    conn = sqlite3.Connection(db_path)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn

def _init_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            value TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_name ON items(name)
    """)
    conn.commit()
```

### Configuration Files

Use YAML for configuration:

```python
import yaml
from pathlib import Path

def load_config() -> dict:
    """Load configuration from YAML file."""
    config_path = Path.home() / ".agent-kit" / "newtool.yaml"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f)
```

### Output Formatting

Use Rich for colorful, formatted output:

```python
from rich.console import Console
from rich.table import Table

console = Console()

# Simple colored output
console.print("[green]Success![/green]")
console.print("[red]Error:[/red] Something went wrong")
console.print("[dim]Debug info[/dim]")

# Tables
table = Table(show_header=True)
table.add_column("Name")
table.add_column("Value")
table.add_row("item1", "value1")
table.add_row("item2", "value2")
console.print(table)
```

### JSON Output

Support JSON output for programmatic use:

```python
import json

@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def list_cmd(json_output: bool) -> None:
    """List items."""
    items = get_items()
    
    if json_output:
        data = [{"id": i.id, "name": i.name} for i in items]
        print(json.dumps(data, indent=2))
    else:
        # Rich formatted output
        for item in items:
            console.print(f"[cyan]{item.name}[/cyan]: {item.value}")
```

### Input Validation

Create validation functions with clear error messages:

```python
import re

def validate_name(name: str) -> None:
    """Validate name format.
    
    Raises:
        ValueError: If name is invalid.
    """
    if not re.match(r"^[a-z0-9-]+$", name):
        raise ValueError(
            f"'{name}' must contain only lowercase letters, numbers, and hyphens"
        )
```

### Stdin Input

Support reading from stdin for automation:

```python
import sys

@click.argument("value")
def set_cmd(value: str) -> None:
    """Set a value."""
    if value == "-":
        value = sys.stdin.read()
    
    value = value.strip()
    # Process value...
```

## Testing

### Test Structure

- One test file per module
- Use pytest fixtures for setup/teardown
- Test both success and error cases
- Use temporary databases for isolation

```python
import tempfile
from pathlib import Path
import pytest

@pytest.fixture
def temp_db(monkeypatch):
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setattr("agent_kit.newtool.db.get_db_path", lambda: db_path)
        yield db_path

def test_add_item(temp_db):
    """Test adding an item."""
    item_id = db.add_item("test-item", "test-value")
    assert item_id == 1
```

### CLI Testing

Use Click's test runner:

```python
from click.testing import CliRunner

def test_command():
    """Test CLI command."""
    runner = CliRunner()
    result = runner.invoke(main, ["subcommand", "arg"])
    assert result.exit_code == 0
    assert "expected output" in result.output
```

### Running Tests

```bash
# All tests
uv run python -m pytest

# Specific module
uv run python -m pytest tests/newtool/

# With coverage
uv run python -m pytest --cov=agent_kit

# Verbose output
uv run python -m pytest -v
```

## Code Quality

### Linting

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# With unsafe fixes
uv run ruff check --fix --unsafe-fixes .
```

**Configuration:** See `[tool.ruff]` in `pyproject.toml`
- Line length: 100
- Target: Python 3.13
- Selected rules: E, F, I, N, W, UP

### Formatting

```bash
# Format code
uv run black .

# Check without modifying
uv run black --check .
```

**Configuration:** See `[tool.black]` in `pyproject.toml`
- Line length: 100
- Target: Python 3.13

### Type Checking

```bash
# Type check
uv tool run mypy src/agent_kit/newtool/
```

**Configuration:** See `[tool.mypy]` in `pyproject.toml`
- Strict mode enabled
- Python 3.13

## Expectations

### Before Submitting

1. **Tests pass:** All tests must pass
2. **Linting clean:** No ruff errors
3. **Type hints:** Add type annotations to functions
4. **Documentation:** Update README.md with new tool usage
5. **Test coverage:** Add tests for new functionality

### Code Style

- Use type hints for function parameters and return values
- Keep functions focused and small
- Use descriptive variable names
- Add docstrings to public functions
- Handle errors gracefully with clear messages

### Commit Messages

- Use clear, descriptive commit messages
- Reference issues when applicable
- Keep commits focused on single changes

## Dependencies

### Core Dependencies

- **click** - CLI framework
- **rich** - Terminal formatting
- **httpx** - HTTP client (for oauth/notion)
- **pyyaml** - YAML parsing
- **mcp** - Model Context Protocol (for notion)

### Dev Dependencies

- **ruff** - Linting
- **black** - Formatting
- **mypy** - Type checking
- **pytest** - Testing

Add new dependencies to `pyproject.toml`:

```toml
[project]
dependencies = [
    "new-package>=1.0.0",
]

[dependency-groups]
dev = [
    "new-dev-package>=1.0.0",
]
```

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG (if exists)
3. Run full test suite
4. Tag release: `git tag v0.x.0`
5. Push: `git push --tags`
