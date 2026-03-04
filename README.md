# CLI Tools

A monorepo of small, focused Python CLI tools for common development tasks.

## Purpose

This repository provides a collection of lightweight, single-purpose command-line utilities. Each tool is independently installable and follows consistent patterns for ease of use and maintenance.

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager

## Available Tools

### [kv](./kv/)

A simple key-value store with expiry support, backed by SQLite. Store and retrieve values with optional TTL, perfect for temporary state or configuration management.

### [oauth](./oauth/)

OAuth authentication for SaaS providers. Handles OAuth 2.0 flows with PKCE, dynamic endpoint discovery, and stores credentials securely using the kv tool.

### [notion](./notion/)

CLI tool for searching and fetching Notion pages via MCP. Supports multiple output formats (terminal markdown, raw markdown, JSON) and integrates with the oauth tool for authentication.

## Repository Structure

```
cli-tools/
├── pyproject.toml          # Workspace config with shared dependencies
├── .venv/                  # Shared virtual environment
└── <tool-name>/            # Each tool in its own directory
    ├── pyproject.toml      # Tool-specific dependencies and metadata
    ├── README.md           # Tool documentation
    ├── src/<tool-name>/    # Source code
    │   ├── __init__.py
    │   ├── cli.py          # CLI interface (using click)
    │   └── ...
    └── tests/              # Tests
```

## Tooling

All tools in this repository use:

- **uv** - Package management and virtual environments
- **click** - CLI framework
- **rich** - Terminal formatting (where appropriate)
- **ruff** - Linting
- **black** - Code formatting
- **mypy** - Type checking
- **pytest** - Testing

Shared dependencies are managed at the workspace level to ensure consistency.

## Development

### Setup

```bash
# Clone and sync dependencies
uv sync
```

### Installing Tools

```bash
# Install a tool globally
uv tool install ./<tool-name>

# Or run without installing
uvx --from ./<tool-name> <tool-name> --help
```

### Running Tests

```bash
# All tests
uv run pytest

# Specific tool
cd <tool-name> && uv run pytest
```

### Code Quality

```bash
# Format code
uv run black .

# Lint
uv run ruff check .

# Type check
uv run mypy .
```

## Contributing

When adding a new tool:

1. Create a new directory with the tool name
2. Add `pyproject.toml` with tool metadata and dependencies
3. Use `src/<tool-name>/` layout for source code
4. Implement CLI using click, use rich for output formatting
5. Add comprehensive tests (unit + integration)
6. Create detailed README.md in the tool directory
7. Update this README to list the new tool
