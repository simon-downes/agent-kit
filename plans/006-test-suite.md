# 006: Agent-Kit Test Suite

## Objective

Establish a comprehensive test suite for agent-kit covering all integrations (Slack,
Linear, Jira, Notion, Google, Brain) and shared infrastructure (auth, config, errors).
Uses consistent patterns with shared fixtures, mocking all external dependencies. Tests
must pass without network access or credentials.

## Requirements

- MUST use pytest as the test runner (already a dev dependency)
- MUST mock all external HTTP calls — no live API calls in tests
  - AC: Tests pass without network access or credentials
- MUST use respx for mocking httpx-based integrations (Linear, Jira, Slack, Google)
  - Why: respx is the standard httpx mock library, integrates cleanly with pytest
- MUST use unittest.mock.AsyncMock for Notion (MCP session, not httpx)
- MUST use pytest-asyncio for testing Notion async client functions directly
- MUST use unittest.mock for non-HTTP externals (subprocess for Brain git/rg, fcntl.flock)
- MUST test each integration at three layers:
  1. Data transformation — given raw API response, verify transformed output
  2. CLI commands — via Click's CliRunner, verify argument parsing, output shape, exit codes
  3. Error handling — auth failures, rate limits, scope violations, missing config
  - AC: Each integration has tests for all three layers
- MUST provide shared fixtures in `tests/conftest.py`:
  - `mock_config` — factory fixture, patches `load_config()` with overrides
  - `mock_credentials` — patches `get_field()`/`set_field()` against in-memory dict
  - `cache_dir` — `tmp_path / "cache"`, patches Slack's `_get_cache_dir()`
  - `cli_runner` — `click.testing.CliRunner(mix_stderr=False)`
  - AC: Fixtures importable from conftest, used consistently across all test files
- MUST test shared infrastructure independently (errors, config, auth)
- MUST test pagination logic for integrations that paginate (Slack, Linear, Jira, Google)
  - AC: Tests verify page accumulation, limit enforcement, max page guard, empty page handling
- MUST test Slack caching logic — TTL expiry, cache miss, `--no-cache` bypass, file corruption recovery
  - AC: Cache tests use `tmp_path`, no real filesystem side effects
- MUST follow consistent test file structure mirroring `src/agent_kit/`
- MAY use pytest.mark.parametrize for testing multiple similar scenarios

## Technical Design

### Dependencies

Add to `[dependency-groups] dev` in `pyproject.toml`:
- `respx>=0.22.0` — httpx mock library
- `pytest-asyncio>=0.25.0` — async test support for Notion

Run `uv sync` after adding to update the lock file.

### Pytest config

Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

### Test structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_config.py           # config.py: _deep_merge, load_config, save_config
├── test_errors.py           # errors.py: handle_errors, exit codes, output()
├── auth/
│   ├── test_credentials.py  # Credential CRUD, get_field/set_field, permissions
│   └── test_oauth.py        # PKCE generation, token exchange, refresh, _store_tokens
├── slack/
│   ├── test_api.py          # api_get, api_post, paginated_get, rate limits, token cache
│   ├── test_cli.py          # CLI commands via CliRunner
│   └── test_resolve.py      # File cache, in-memory cache, resolution, user lookup
├── linear/
│   ├── test_client.py       # GraphQL calls, pagination, response transform, resolve
│   └── test_cli.py          # CLI commands
├── jira/
│   ├── test_client.py       # REST calls, ADF conversion, pagination, resolve
│   └── test_cli.py          # CLI commands
├── notion/
│   ├── test_client.py       # MCP tool calls, scope checking, response parsing, filters
│   └── test_cli.py          # CLI commands
├── google/
│   ├── test_auth.py         # Token refresh, expiry detection
│   ├── test_mail.py         # Response transformation, HTML→markdown
│   ├── test_calendar.py     # Response transformation
│   ├── test_drive.py        # Response transformation, export logic
│   └── test_cli.py          # CLI commands
└── brain/
    ├── test_client.py       # Index management, search ranking, git ops, file locking
    └── test_cli.py          # CLI commands
```

### Mocking strategy

| Integration | HTTP layer | Auth | Other |
|---|---|---|---|
| Slack | respx: `https://slack.com/api/*` | `mock_credentials` with fake `access_token` | `cache_dir` fixture |
| Linear | respx: `POST https://api.linear.app/graphql` | `mock_credentials` with fake `token` | — |
| Jira | respx: `https://api.atlassian.com/*` | `mock_credentials` with fake `email`, `token`, `cloud_id` | — |
| Google | respx: `https://www.googleapis.com/*`, `https://oauth2.googleapis.com/*` | `mock_credentials` with fake tokens + `expires_at` | `mock.patch` for pandoc subprocess |
| Notion | `AsyncMock` on `ClientSession` (passed as param to client functions) | `mock_credentials` with fake `access_token` | — |
| Brain | `mock.patch` on `subprocess.run` for git/rg | None | `tmp_path` for filesystem, `mock.patch` for `fcntl.flock` |

### Module globals to reset between tests

Autouse fixture in `conftest.py` must reset after each test:
- `slack.api._cached_token`
- `slack.resolve._cache_dir`, `_user_cache`, `_channel_cache`, `_dm_cache`
- `google.auth._cached_token`

### Module-level constants to patch

- `auth/__init__.py`: `CREDENTIALS_PATH`, `AGENT_KIT_HOME` → `tmp_path`
- `config.py`: `CONFIG_PATH` → `tmp_path / "config.yaml"`
- Handle `sys.exit()` calls in config error paths — tests must catch `SystemExit`

### CLI test pattern

All CLI tests follow the same shape:
1. Set up mocks (respx routes or mock patches)
2. Invoke via `cli_runner.invoke(command_group, ["subcommand", "--option", "value"])`
3. Assert exit code, parse `result.output` as JSON, verify keys/shape
4. For error cases: assert exit code and check `result.output` for error message

### Conventions

- One test file per source file (mirrors `src/` structure)
- Test functions: `test_<function_or_command>_<scenario>`
- `pytest.mark.asyncio` only for Notion client tests
- `respx.mock` decorator on test functions, not module-level
- Each test independent — no ordering, no shared mutable state
- Response fixtures as dicts at top of each test file (keeps context local)

### Not testing

- Live API calls (all mocked)
- OAuth browser flow / callback server (test PKCE, exchange, refresh as unit functions)
- MCP server behaviour (mock at session level)
- Webhook delivery (test payload construction only)

## Milestones

1. **Test infrastructure and shared modules**
   Approach:
   - Add `respx>=0.22.0` and `pytest-asyncio>=0.25.0` to dev dependencies
   - Add `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` and `testpaths = ["tests"]`
   - Build `conftest.py` with shared fixtures and autouse global reset
   - `mock_config` is a factory: `mock_config(overrides)` merges with DEFAULT_CONFIG and patches `load_config`
   - `mock_credentials` patches `get_field` to read from in-memory dict
   - Autouse fixture resets: `slack.api._cached_token`, `slack.resolve._cache_dir`, `_user_cache`, `_channel_cache`, `_dm_cache`, `google.auth._cached_token`
   - ⚠️ `config.py` uses module-level `CONFIG_PATH` and calls `sys.exit(1)` on errors — patch the constant, catch `SystemExit`
   Tasks:
   - Add test dependencies to `pyproject.toml`, run `uv sync`
   - Add pytest config to `pyproject.toml`
   - Create `tests/conftest.py` with shared fixtures and autouse global reset
   - Create `tests/test_config.py` — `_deep_merge`, `load_config` (missing file, overrides, malformed), `save_config`
   - Create `tests/test_errors.py` — `handle_errors` for each exception type/exit code, `output()` JSON
   Deliverable: Shared test infrastructure in place, config and error tests passing.
   Verify: `uv run pytest tests/test_config.py tests/test_errors.py -v` passes

2. **Auth tests**
   Approach:
   - Patch `CREDENTIALS_PATH` and `AGENT_KIT_HOME` to `tmp_path` for filesystem isolation
   - OAuth unit tests: `generate_pkce` (pure function, verify format + S256 hash), `exchange_code` (respx mock token endpoint, with/without client_secret), `refresh_token` (respx mock), `_store_tokens` with nested dot-paths (Slack's `authed_user.access_token`)
   - ⚠️ `credentials.yaml` uses `os.chmod(0o600)` — verify permission handling in tests
   Tasks:
   - Create `tests/auth/test_credentials.py` — `get_field`, `set_field`, `set_fields`, `load_credentials` (missing file, valid file), permission handling
   - Create `tests/auth/test_oauth.py` — `generate_pkce`, `exchange_code`, `refresh_token`, `_store_tokens` with nested paths
   Deliverable: Auth credential and OAuth logic fully tested.
   Verify: `uv run pytest tests/auth/ -v` passes

3. **Slack tests**
   Approach:
   - respx routes for `https://slack.com/api/*`
   - `test_api.py`: `api_get`/`api_post` dispatch, 429 handling (verify Retry-After in message, `_cached_token` cleared on auth errors), `paginated_get` (multi-page, empty page break, max page guard, limit enforcement, 3s sleep between pages)
   - `test_resolve.py`: use `cache_dir` fixture. File cache: write, read, TTL expiry (manipulate timestamp), corruption (write invalid JSON), `--no-cache` bypass. In-memory cache hit/miss. `resolve_channel` for `#name`, `@user` (verify POST to conversations.open), raw ID. `get_channels`/`get_dms` filtering (archived, group). `get_users` with deleted/bot filtering.
   - `test_cli.py`: full stack via CliRunner + respx. Each command: `channels`, `dms`, `history`, `thread`, `search`, `users`, `send`. Verify output shape, `--limit`, `--archived`, `--group`, `--no-cache`, `--since`.
   - ⚠️ Reset all module globals between tests (handled by autouse fixture from milestone 1)
   Tasks:
   - Create `tests/slack/test_api.py`
   - Create `tests/slack/test_resolve.py`
   - Create `tests/slack/test_cli.py`
   Deliverable: Slack integration fully tested at all three layers.
   Verify: `uv run pytest tests/slack/ -v` passes

4. **Linear tests**
   Approach:
   - respx route for `POST https://api.linear.app/graphql` — match on request body to return different responses per query
   - `test_client.py`: `LinearClient` methods, GraphQL response flattening, cursor pagination in `get_issues`, error handling. Include `resolve.py` functions: `resolve_status`, `resolve_assignee`, `resolve_labels`, `resolve_team_id`.
   - `test_cli.py`: each command via CliRunner — `teams`, `team`, `projects`, `issues`, `issue`, `create-issue`, `update-issue`, `comments`, `comment`, `upload`
   Tasks:
   - Create `tests/linear/test_client.py`
   - Create `tests/linear/test_cli.py`
   Deliverable: Linear integration fully tested.
   Verify: `uv run pytest tests/linear/ -v` passes

5. **Jira tests**
   Approach:
   - respx routes for `https://api.atlassian.com/ex/jira/*/rest/api/3/*`
   - `test_client.py`: `JiraClient` methods, JQL query building, pagination, status transitions. ADF↔text conversion (`adf_to_text`, `text_to_adf`) — parametrize with nested structures, empty docs, inline formatting. Include `resolve.py`: `resolve_assignee`, `resolve_transition`.
   - `test_cli.py`: each command via CliRunner — `projects`, `project`, `statuses`, `issues`, `issue`, `create-issue`, `update-issue`, `transition`, `comments`, `comment`, `attach`
   - ⚠️ ADF conversion edge cases — parametrize these
   Tasks:
   - Create `tests/jira/test_client.py`
   - Create `tests/jira/test_cli.py`
   Deliverable: Jira integration fully tested.
   Verify: `uv run pytest tests/jira/ -v` passes

6. **Notion tests**
   Approach:
   - Mock `ClientSession` with `AsyncMock` — Notion client functions accept session as a parameter, pass mock directly
   - `test_client.py`: MCP tool call wrappers, scope enforcement (ancestor page ID checking against allowlist), response parsing. Include `filters.py`: `parse_filter` with all three operators (`=`, `!=`, `~=`) and error path.
   - `test_cli.py`: via CliRunner (Click handles asyncio.run bridge) — `search`, `page`, `db`, `query`, `comments`, `create-page`, `update-page`, `comment`
   - ⚠️ Scope checking extracts page IDs from XML-like MCP responses — need representative fixtures
   Tasks:
   - Create `tests/notion/test_client.py`
   - Create `tests/notion/test_cli.py`
   Deliverable: Notion integration fully tested.
   Verify: `uv run pytest tests/notion/ -v` passes

7. **Google tests**
   Approach:
   - respx routes for `https://www.googleapis.com/*` and `https://oauth2.googleapis.com/*`
   - `test_auth.py`: token refresh logic, expiry detection (within 60s window), 401 retry
   - `test_mail.py`: response transformation, HTML→markdown (mock pandoc subprocess)
   - `test_calendar.py`: response transformation
   - `test_drive.py`: response transformation, export format selection, download logic
   - `test_cli.py`: each subcommand group via CliRunner — `mail {search,recent,unread,read}`, `calendar {today,upcoming,event}`, `drive {search,recent,list,fetch}`
   - ⚠️ Three sub-services with different response shapes — keep fixtures per-file
   Tasks:
   - Create `tests/google/test_auth.py`
   - Create `tests/google/test_mail.py`, `test_calendar.py`, `test_drive.py`
   - Create `tests/google/test_cli.py`
   Deliverable: Google integration fully tested.
   Verify: `uv run pytest tests/google/ -v` passes

8. **Brain tests**
   Approach:
   - `tmp_path` for all filesystem operations — create temp brain directory structures
   - `mock.patch` on `subprocess.run` for git and rg — return realistic stdout/stderr
   - `mock.patch` on `fcntl.flock` for file locking tests
   - `test_client.py`: index management (build, read, update), search ranking (weighted results), YAML frontmatter parsing, git operations, file locking. Focus on public API.
   - `test_cli.py`: each command via CliRunner — `init`, `index`, `search`, `reindex`, `commit`, `project`, `status`, `validate`
   Tasks:
   - Create `tests/brain/test_client.py`
   - Create `tests/brain/test_cli.py`
   Deliverable: Brain integration fully tested.
   Verify: `uv run pytest tests/brain/ -v` passes

9. **Full suite validation and project.py**
   Approach:
   - Add `tests/test_project.py` — test `resolve_project_name()` branches (project_dir, git remote, cwd fallback), mock subprocess for git calls
   - Run complete suite, fix cross-test interference (leaked globals, fixture conflicts)
   - Verify no tests require network or credentials
   Tasks:
   - Create `tests/test_project.py`
   - Run `uv run pytest tests/ -v`, fix any failures
   - Document test running in `agent-kit/CONTRIBUTING.md`
   Deliverable: Full test suite green, documented.
   Verify: `uv run pytest tests/ -v` passes with all tests green
