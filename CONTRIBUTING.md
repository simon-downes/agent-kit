# Contributing to Agent Kit

Guidelines for developing new tools and maintaining the codebase.

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager

## Setup

```bash
git clone https://github.com/simon-downes/agent-kit.git
cd agent-kit
uv sync
uv tool install --editable .
```

## Project Structure

```
agent-kit/
├── pyproject.toml              # Package configuration
├── src/agent_kit/
│   ├── cli.py                  # Main CLI entry point
│   ├── project.py              # Project name resolution
│   ├── check/                  # Environment check tool
│   ├── kv/                     # Key-value store tool
│   ├── log/                    # Activity log tool
│   ├── oauth/                  # OAuth authentication
│   ├── notion/                 # Notion integration
│   └── commands/               # Standalone commands (project)
└── tests/
    ├── check/
    ├── kv/
    ├── log/
    ├── commands/
    └── ...
```

Each tool is a module with:
- `cli.py` - Click command group and subcommands
- `db.py` - Database operations (if needed)
- `models.py` - Data models and validation (if needed)
- `formatters.py` - Output formatting (if needed)

## Adding a New Tool

1. **Create module structure** in `src/agent_kit/newtool/`
2. **Implement CLI** using Click command groups (see existing tools)
3. **Register command** in `src/agent_kit/cli.py`
4. **Add tests** in `tests/newtool/`
5. **Update README.md** with usage examples

Examine existing tools (`kv`, `log`) for reference implementations.

## Common Patterns

### CLI Framework
- Use Click for command-line interface
- Organize as command groups with subcommands
- Support `--help` on all commands

### Data Storage
- SQLite for persistent storage
- Store databases in `~/.agent-kit/<tool>/`
- Initialize schema on first connection
- Use indexes for query performance

### Configuration
- YAML files for configuration
- Store in `~/.agent-kit/`

### Output Formatting
- Rich for colorful terminal output
- Support `--json` flag for programmatic use
- Clear error messages with actionable guidance

### Input Handling
- Support stdin with `-` argument for automation
- Validate inputs with clear error messages
- Strip leading/trailing whitespace appropriately

### Error Handling
- Catch exceptions and show user-friendly messages
- Use appropriate exit codes (0=success, 1=error, 2=not found)
- Print errors to stderr using Rich console

## Testing

### Structure
- One test file per module (`test_cli.py`, `test_db.py`, etc.)
- Use pytest fixtures for setup/teardown
- Test both success and error cases
- Use temporary databases for isolation

### Running Tests

```bash
# All tests
uv run python -m pytest

# Specific module
uv run python -m pytest tests/log/

# Verbose
uv run python -m pytest -v
```

## Code Quality

### Linting
```bash
uv run ruff check .
uv run ruff check --fix .
```

Configuration: `[tool.ruff]` in `pyproject.toml`
- Line length: 100
- Target: Python 3.13

### Formatting
```bash
uv run black .
```

Configuration: `[tool.black]` in `pyproject.toml`

### Type Checking
```bash
uv tool run mypy src/agent_kit/
```

Configuration: `[tool.mypy]` in `pyproject.toml`

## Expectations

Before submitting:
1. All tests pass
2. No linting errors
3. Type hints on functions
4. README.md updated with usage
5. Tests cover new functionality

Code style:
- Type hints for parameters and return values
- Descriptive names
- Docstrings on public functions
- Clear error messages
- Small, focused functions

## Dependencies

Core:
- **click** - CLI framework
- **rich** - Terminal formatting
- **httpx** - HTTP client
- **pyyaml** - YAML parsing
- **mcp** - Model Context Protocol

Dev:
- **ruff** - Linting
- **black** - Formatting
- **mypy** - Type checking
- **pytest** - Testing

Add dependencies to `pyproject.toml` under `[project]` or `[dependency-groups]`.
