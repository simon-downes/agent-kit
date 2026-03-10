# Agent Kit

A unified CLI toolkit for development workflows, providing key-value storage, OAuth authentication, and Notion integration.

## Purpose

Agent Kit provides a collection of focused command-line utilities under a single `ak` command. Each tool is designed for a specific purpose and they integrate seamlessly with each other.

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager

## Available Tools

### [kv](./src/agent_kit/kv/)

A simple key-value store with expiry support, backed by SQLite. Store and retrieve values with optional TTL, perfect for temporary state or configuration management.

### [oauth](./src/agent_kit/oauth/)

OAuth authentication for SaaS providers. Handles OAuth 2.0 flows with PKCE, dynamic endpoint discovery, and stores credentials securely using the kv tool.

### [notion](./src/agent_kit/notion/)

CLI tool for searching and fetching Notion pages via MCP. Supports multiple output formats (terminal markdown, raw markdown, JSON) and integrates with the oauth tool for authentication.

## Installation

```bash
# Install from local directory
uv tool install .

# Or install from GitHub
uv tool install git+https://github.com/simon-downes/cli-tools.git
```

## Usage

```bash
# Key-value store
ak kv set my-key "my value"
ak kv get my-key
ak kv list

# OAuth authentication
ak oauth login notion
ak oauth status notion
ak oauth logout notion

# Notion integration
ak notion search "project notes"
ak notion fetch <page-id>
```

## Repository Structure

```
agent-kit/
├── pyproject.toml          # Package configuration
├── src/agent_kit/          # Source code
│   ├── cli.py              # Main CLI entry point
│   ├── kv/                 # Key-value store
│   ├── oauth/              # OAuth authentication
│   └── notion/             # Notion integration
└── tests/                  # Tests
    ├── kv/
    ├── oauth/
    └── notion/
```

## Configuration

All configuration and data is stored in `~/.agent-kit/`:
- `db` - SQLite database for key-value store
- `oauth.yaml` - OAuth provider configurations
- `notion.yaml` - Notion configuration (if applicable)

## Tooling

- **uv** - Package management and virtual environments
- **click** - CLI framework
- **rich** - Terminal formatting
- **ruff** - Linting
- **black** - Code formatting
- **mypy** - Type checking
- **pytest** - Testing

## Development

### Setup

```bash
# Clone and sync dependencies
git clone https://github.com/simon-downes/cli-tools.git
cd cli-tools
uv sync
```

### Running Tests

```bash
# All tests
uv run pytest

# Specific module
uv run pytest tests/kv/
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
