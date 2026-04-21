# Contributing

## Development Setup

```bash
cd agent-kit
uv sync --extra dev
uv run ak --help
```

## Repository Layout

```
src/agent_kit/
├── cli.py              # Top-level Click group — registers subcommand groups
├── config.py           # Config loading (~/.agent-kit/config.yaml), defaults, deep merge
├── errors.py           # Exception hierarchy, shared output(), @handle_errors decorator
├── mcp.py              # Generic MCP session context manager
├── project.py          # Project name resolution
├── auth/               # Credential management
│   ├── __init__.py     # Credential store (YAML I/O, file permissions)
│   ├── cli.py          # Auth subcommands (set, import, login, refresh, status)
│   ├── oauth.py        # OAuth2 + PKCE flow
│   └── providers.yaml  # Bundled OAuth provider definitions
├── brain/              # Second brain management
│   ├── cli.py          # Brain subcommands (search, index, status, validate)
│   ├── client.py       # BrainClient class — public interface
│   ├── index.py        # Private — index/reindex/metadata extraction
│   ├── search.py       # Private — search ranking, ripgrep integration
│   └── git.py          # Private — git operations
├── notion/             # Notion integration (async MCP)
│   ├── cli.py          # Notion subcommands
│   ├── client.py       # Async MCP functions, scope checks
│   └── filters.py      # Post-processing filter parsing
├── linear/             # Linear integration
│   ├── cli.py          # Linear subcommands
│   ├── client.py       # LinearClient class — GraphQL queries and mutations
│   └── resolve.py      # Name → ID resolution (statuses, assignees, labels)
├── jira/               # Jira integration
│   ├── cli.py          # Jira subcommands
│   ├── client.py       # JiraClient class — REST API, ADF conversion
│   └── resolve.py      # Name → ID resolution (assignees, transitions)
├── google/             # Google Workspace integration
│   ├── cli.py          # Google subcommands (mail, calendar, drive)
│   ├── client.py       # GoogleClient class — auth, refresh, public methods
│   ├── mail.py         # Private — Gmail API implementation
│   ├── calendar.py     # Private — Calendar API implementation
│   └── drive.py        # Private — Drive API implementation
└── slack/              # Slack integration
    ├── cli.py          # Slack subcommands (channels, dms, history, search, send)
    ├── client.py       # SlackClient class — Web API and webhooks
    └── resolve.py      # Channel/user resolution and file-based caching
```

## Architecture

### Layers

Each integration has two required files and optional extras:

- **client.py** — Client class as the public interface. All API methods are class methods.
  Public methods above the `# --- Private implementation ---` marker, private below.
  Never calls `sys.exit()`, never formats output.
- **cli.py** — Click commands that construct the client via `_get_client()`, call methods,
  and format output. Error handling via `@handle_errors`. No business logic.
- **resolve.py** — Optional. Name→ID resolution and caching when needed (Slack, Linear, Jira).

### Client Class Pattern

Every HTTP integration has a client class in `client.py`:

```python
"""Service description."""

class FooClient:
    """Client for Foo API."""

    def __init__(self, token: str):
        self._token = token

    # --- Public interface ---

    def get_things(self, *, limit: int = 50) -> list[dict]: ...
    def get_thing(self, identifier: str) -> dict: ...
    def create_thing(self, *, title: str) -> dict: ...

    # --- Private implementation ---

    def _request(self, method: str, path: str, **kwargs) -> dict: ...
    def _paginate(self, ...) -> list: ...
    def _format_thing(self, raw: dict) -> dict: ...
```

The class holds state (token, HTTP client) — no module-level globals for auth.
Implementation can live in the class or in separate private modules (e.g. Google
delegates to mail.py, calendar.py, drive.py; Brain delegates to index.py, search.py, git.py).

**Exception:** Notion uses async MCP, not HTTP. It uses async module functions with
`ClientSession` passed as a parameter. Same public/private layout convention applies.

### Error Handling

All errors flow through a single mechanism defined in `errors.py`:

**Exception hierarchy:**
- `AgentKitError` — base, exit code 1
- `AuthError(AgentKitError)` — credential/auth issues, exit code 2
- `ConfigError(AgentKitError)` — configuration issues, exit code 1
- `ScopeError(AgentKitError)` — resource outside configured scope, exit code 1

**The `@handle_errors` decorator** is applied to every Click command. It catches all known
exception types and exits with the appropriate code and message. Client code raises
exceptions; the decorator handles them at the CLI boundary.

```python
@linear.command()
@handle_errors
def teams() -> None:
    """List all teams."""
    output(get_teams(_get_client()))
```

No try/except in command functions. No `sys.exit()` in client code.

### Output

- `output(data)` from `errors.py` — writes JSON to stdout (`json.dumps(data, indent=2)`)
- `print("OK")` — for simple confirmations where JSON would be wasteful
- `print(..., file=sys.stderr)` — errors and progress messages only
- Prefer token-efficient output — don't wrap simple results in unnecessary structure

### Config

`config.py` provides `load_config()` which returns a dict deep-merged with `DEFAULT_CONFIG`.
Services read their config section as a plain dict — no dataclasses.

```python
config = load_config()
enabled = config.get("notion", {}).get("read", {}).get("enabled", True)
```

`save_config(data)` writes back to `~/.agent-kit/config.yaml`. Used by the OAuth flow to
persist discovered endpoints.

### Credentials

`auth/__init__.py` provides `get_field(service, field)`, `set_field(service, field, value)`,
and `set_fields(service, fields)`. Credentials live in `~/.agent-kit/credentials.yaml`
(mode 0600).

Service CLI modules resolve credentials with a fallback chain:

```python
token = get_field("notion", "access_token") or os.environ.get("NOTION_TOKEN")
if not token:
    raise AuthError("no Notion credentials — run 'ak auth set notion access_token'")
```

Credential store first, environment variable fallback, actionable error message.

### Async (Notion only)

Notion uses MCP which requires async. The pattern is:

```python
@notion.command()
@handle_errors
def example() -> None:
    async def _do():
        async with _session(token) as session:
            return await search(session, query)
    output(_run(_do()))
```

`_run()` bridges to `asyncio.run()`. The `@handle_errors` decorator unwraps
`ExceptionGroup` from anyio/MCP task groups automatically.

Linear and Slack are synchronous (plain httpx).

## Adding a New Service

1. Create `src/agent_kit/<service>/` with `__init__.py`, `cli.py`, `client.py`
2. **client.py** — Client class with public/private split:
   - Constructor takes credentials (token, API key, etc.)
   - Public methods above `# --- Private implementation ---` marker
   - Raise `AuthError` for credential issues, `ValueError` for not-found/validation
   - Let `httpx.HTTPStatusError` propagate for HTTP errors
3. **cli.py** — Click subcommand group with `@handle_errors` on every command
   - `_get_client()` constructs the client from credential store
   - Commands are thin: construct client → call method → `output()` result
4. Register the group in `src/agent_kit/cli.py`: `main.add_command(<service>)`
5. Add credential config to `DEFAULT_CONFIG` in `config.py` under `auth`
6. Add tests in `tests/<service>/` (test_client.py, test_cli.py)
7. Add `docs/<service>.md` with full command reference
8. Add summary to `README.md` tools section

### Credential getter pattern

```python
def _get_client() -> ServiceClient:
    """Get client from credential store or environment."""
    from agent_kit.auth import get_field

    key = get_field("myservice", "token") or os.environ.get("MYSERVICE_TOKEN")
    if not key:
        raise AuthError("no MyService credentials — run 'ak auth set myservice token'")
    return ServiceClient(key)
```

### Access control pattern (if applicable)

```python
from agent_kit.errors import ConfigError

def require_write(config: dict) -> None:
    if not config.get("myservice", {}).get("write", {}).get("enabled", False):
        raise ConfigError("MyService write operations are disabled in config")
```

## Adding a Command to an Existing Service

1. Add the API call in `client.py` — raise exceptions on errors
2. Add the Click command in `cli.py` with `@handle_errors`
3. Gate writes with `require_write()`, reads with `require_read()` if applicable
4. Update `docs/<service>.md`

## Testing

```bash
uv run pytest tests/ -v
```

Tests mock all external dependencies — no network or credentials required.

- **respx** for httpx-based integrations (Slack, Linear, Jira, Google)
- **AsyncMock** for Notion MCP sessions
- **unittest.mock.patch** for subprocess (Brain git/rg) and filesystem
- **tmp_path** for cache and credential file tests

Shared fixtures in `tests/conftest.py`: `mock_config`, `mock_credentials`, `cache_dir`,
`cli_runner`. Module globals are auto-reset between tests.

## Code Style

Uses [ruff](https://docs.astral.sh/ruff/) (line length 100, Python 3.11 target).

```bash
uv run ruff check src/ && uv run ruff format --check src/
```

## Commit Messages

[Conventional commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`.
