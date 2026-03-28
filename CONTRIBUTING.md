# Contributing

## Key Rules

- Credentials come from environment variables — never implement auth flows in agent-kit
- All command output is JSON to stdout, errors to stderr — no `rich` or colour output
- Each service is a subcommand group (`ak <service> <command>`)
- Write operations must check config permissions before executing
- Scope checks happen after fetching — the response includes ancestor data used for validation

## Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

### Setup

```bash
cd agent-kit
uv sync
uv run ak --help
```

### Verify

```bash
uv run ak --version
uv run ak notion --help
```

## Project Conventions

### Code Organisation

```
src/agent_kit/
├── cli.py            # Top-level Click group — registers service subcommands
├── config.py         # Config loading, defaults, dataclasses
├── mcp.py            # Generic MCP session context manager (not service-specific)
└── <service>/        # One directory per service
    ├── cli.py        # Click subcommands
    ├── client.py     # API/MCP calls, response parsing, scope checks
    └── filters.py    # Post-processing filter parsing for query results
```

### Adding a New Service

1. Create `src/agent_kit/<service>/` with `__init__.py`, `cli.py`, `client.py`
2. Register the subcommand group in `src/agent_kit/cli.py`
3. Add default config in `DEFAULT_CONFIG` in `config.py`
4. Add config dataclasses following the `NotionConfig` pattern
5. Update README with command reference

### Adding a Command to an Existing Service

1. Add the MCP/API call in `client.py`
2. Add the Click command in `cli.py`
3. Gate writes with `require_write()`, reads with `require_read()`
4. Check scope after fetching (responses include ancestor data for validation)
5. Update README

### Code Style

Uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting. Configured in `pyproject.toml` (line length 100, Python 3.11 target).

```bash
# Check
uv run ruff check src/
uv run ruff format --check src/

# Fix
uv run ruff check src/ --fix
uv run ruff format src/
```

### Output Conventions

- JSON to stdout via `json.dumps(data, indent=2)` — must be valid, parseable by `jq`
- Errors to stderr via `print(..., file=sys.stderr)` — plain text, no colour
- Exit codes: 0 success, 1 error/permission, 2 auth failure
- No `rich` dependency — agents are the primary consumer

### Error Handling

- Missing credentials → exit 2 with actionable message
- Permission denied (config-gated) → exit 1
- Scope violation → exit 1
- MCP/API errors → unwrap ExceptionGroups, detect 401/429, exit with appropriate code
- Never leak raw tracebacks to the user

### Async Pattern

MCP requires async. CLI commands bridge with `asyncio.run()`:

```python
@notion.command()
def example() -> None:
    async def _do():
        async with mcp_session(url, headers) as session:
            return await session.call_tool(...)
    _output(_run(_do()))
```

The MCP session in `mcp.py` is a generic `async with` context manager — no manual `__aexit__` calls.

## Testing

```bash
uv run python -m pytest
```

Tests live in `tests/` mirroring `src/` structure.

## Commit Messages

Uses [conventional commits](https://www.conventionalcommits.org/):

- `feat:` — new commands or services
- `fix:` — bug fixes
- `docs:` — documentation
- `chore:` — dependencies, config
