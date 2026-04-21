# 007: Integration Client Refactor

## Objective

Standardise all agent-kit integrations around a consistent client class pattern.
Every integration exposes a client class in `client.py` as its public interface.
Implementation details live behind a clear public/private boundary — either within
the class or in separate private modules. CLI commands are thin wrappers that
construct the client and delegate.

## Requirements

- MUST have a client class in `client.py` for every integration (Slack, Linear,
  Jira, Google, Brain)
  - AC: Each integration has a single class as its public API
- MUST separate public interface from private implementation with a clear marker
  - AC: All public methods appear before private methods in every client.py
- MUST construct clients via `_get_client()` in cli.py for all integrations
  - AC: No module-level token/credential globals; state lives in the client instance
- MUST keep cli.py as a thin layer — argument parsing, client construction, output
  - AC: No business logic in CLI commands
- MUST update all tests to work with the refactored code
  - AC: `uv run pytest tests/ -v` passes with no failures
- MUST NOT change the CLI command interface (command names, arguments, options)
  - AC: All `ak <integration> <command>` invocations work identically
- Notion stays as async module functions (different paradigm) but MUST apply the
  public/private layout convention
  - AC: Public functions above marker, private below

## Technical Design

### Target file structure per integration

```
integration/
├── client.py    # Client class — public methods above marker, private below
├── cli.py       # Click commands — _get_client(), thin delegation to client
└── resolve.py   # Optional — name→ID resolution, caching (takes client instance)
```

### client.py layout convention

```python
"""Integration description."""

class FooClient:
    """Client for Foo API."""

    def __init__(self, token: str): ...

    # --- Public interface ---

    def get_things(self, ...) -> list[dict]: ...
    def get_thing(self, id: str) -> dict: ...
    def create_thing(self, ...) -> dict: ...

    # --- Private implementation ---

    def _request(self, ...) -> dict: ...
    def _paginate(self, ...) -> list: ...
    def _format_thing(self, raw: dict) -> dict: ...
```

### cli.py convention

```python
def _get_client() -> FooClient:
    token = get_field("foo", "token") or os.environ.get("FOO_TOKEN")
    if not token:
        raise AuthError("no credentials — run 'ak auth set foo token'")
    return FooClient(token)
```

### Per-integration design

**Slack** — Major refactor
- Merge `api.py` + `client.py` → `SlackClient` in `client.py`
- Constructor: `SlackClient(token: str, webhook_url: str | None = None)`
- Public methods: `get_channels()`, `get_dms()`, `get_history()`, `get_thread()`,
  `search_messages()`, `get_users()`, `send_message()`, `send_raw()`
- Private: `_get()`, `_post()`, `_paginated_get()`, rate limit handling
- `resolve.py` stays separate — takes `SlackClient` instance, owns caching
- Config/scope checking (`require_read`, `check_channel_scope`) moves to cli.py
  (config is a CLI concern, not a client concern)
- Delete `api.py`

**Linear** — Small refactor
- Move module-level functions into `LinearClient` as methods
- Move `_format_issue`, `_format_issue_detail`, query constants into class
- `resolve.py`: change `client` param type (still `LinearClient`, no signature change)
- `cli.py`: already has `_get_client()`, just update method calls

**Jira** — Small refactor
- Move module-level functions into `JiraClient` as methods
- `adf_to_text`/`text_to_adf` stay as module-level functions (pure transforms,
  no client state needed, used independently)
- Move `_format_issue`, `_format_issue_detail`, `_jql_escape` into class
- `resolve.py`: same pattern as Linear
- `cli.py`: already has `_get_client()`, just update method calls

**Google** — Medium refactor
- Create `GoogleClient` in `client.py`
- Constructor: `GoogleClient(credentials: dict)` — holds token, handles refresh
- Public methods: all mail/calendar/drive functions as flat methods on the class
  (`mail_search()`, `mail_read()`, `calendar_today()`, `drive_fetch()`, etc.)
- Keep `mail.py`, `calendar.py`, `drive.py` as private implementation modules —
  client delegates to them, passing authenticated httpx client
- Absorb `auth.py` into client (token refresh is client state)
- Delete `auth.py`

**Brain** — Medium refactor
- Create `BrainClient` in `client.py`
- Constructor: `BrainClient(brain_dir: Path)`
- Public methods: all current public functions as methods
- Split implementation into private modules:
  - `index.py` — index/reindex/metadata extraction
  - `search.py` — search ranking, ripgrep integration
  - `git.py` — git operations, init, status, commit
- `client.py` delegates to these, keeps validation and simple lookups inline

**Notion** — Layout only
- Reorder `client.py`: public async functions and sync helpers above marker,
  `_extract_*`/`_parse_*`/`_in_scope`/`_fetch_raw` below
- No class (async MCP paradigm)
- No functional changes

## Milestones

1. **Slack refactor**
   Approach:
   - Create `SlackClient` class absorbing `api.py` functions and `client.py` webhook functions
   - Constructor takes `token` and optional `webhook_url`
   - Public methods: `get_channels()`, `get_dms()`, `get_history()`, `get_thread()`,
     `search_messages()`, `get_users()`, `send_message()`, `send_raw()` — the data-fetching
     functions move FROM `resolve.py` INTO the client
   - Private: `_get()`, `_post()`, `_paginated_get()`, rate limit handling
   - Caches (`_user_cache`, `_channel_cache`, `_dm_cache`) become instance attributes on
     `SlackClient`. File-based cache provides persistence across invocations; in-memory
     cache is per-invocation optimisation only.
   - `resolve.py` keeps ONLY resolution and search: `resolve_channel()`, `resolve_user_name()`,
     `search_users()`, plus file cache helpers. Functions accept `SlackClient` instance.
   - Config/scope checking (`require_read`, `check_channel_scope`) moves to cli.py
     (config is a CLI concern, not a client concern)
   - Delete `api.py`
   - ⚠️ ~40 tests need mock target updates — mock at `SlackClient` method level or inject mock transport
   Tasks:
   - Create `SlackClient` class in `client.py`
   - Update `resolve.py` — remove data-fetching functions, accept client instance for resolution
   - Update `cli.py` with `_get_client()` and method calls
   - Delete `api.py`
   - Update all slack tests
   Deliverable: Slack integration uses `SlackClient`, all tests pass.
   Verify: `uv run pytest tests/slack/ -v` passes

2. **Linear refactor**
   Approach:
   - Move `get_teams`, `get_team`, `get_projects`, `get_issues`, `get_issue`,
     `create_issue`, `update_issue`, `get_comments`, `create_comment`, `upload_file`
     from module functions into `LinearClient` methods
   - Move `_format_issue`, `_format_issue_detail` into class as private methods
   - Move query constants into class attributes or keep as module-level (either works,
     class attributes are cleaner)
   - `resolve.py`: update imports — `get_team` becomes `client.get_team()` call.
     Function signatures stay the same (still take `LinearClient` as first arg).
   - `cli.py`: change `get_teams(_get_client())` → `_get_client().get_teams()`
   Tasks:
   - Refactor `client.py` — functions become methods
   - Update `resolve.py` imports (remove `get_team` import, call via client instance)
   - Update `cli.py` call sites
   - Update tests
   Deliverable: Linear functions are methods on `LinearClient`, all tests pass.
   Verify: `uv run pytest tests/linear/ -v` passes

3. **Jira refactor**
   Approach:
   - Same pattern as Linear — move module functions into `JiraClient` methods
   - Keep `adf_to_text`/`text_to_adf` as module-level (pure transforms, no state)
   - Move `_format_issue`, `_format_issue_detail`, `_jql_escape` into class
   - `resolve.py`: update imports — `get_transitions`, `search_users` become client
     method calls. Function signatures stay the same (still take `JiraClient`).
   - `cli.py`: update call sites
   Tasks:
   - Refactor `client.py` — functions become methods
   - Update `resolve.py` imports
   - Update `cli.py` call sites
   - Update tests
   Deliverable: Jira functions are methods on `JiraClient`, all tests pass.
   Verify: `uv run pytest tests/jira/ -v` passes

4. **Google refactor**
   Approach:
   - Create `GoogleClient` in new `client.py`
   - Constructor takes credential dict (token, refresh_token, client_id, client_secret,
     expires_at), creates an internal httpx.Client, handles refresh internally
   - `GoogleClient._request(method, url, **kwargs)` handles 401→refresh→retry in one
     place (replaces the duplicated retry logic in mail.py, calendar.py, drive.py)
   - Public methods delegate to existing service modules, passing `self` (the client)
     so modules call `client._request()` instead of managing auth themselves
   - Service modules (`mail.py`, `calendar.py`, `drive.py`) become private implementation —
     their `_get()` helpers are replaced by `client._request()` calls
   - `require_service` moves to cli.py (config concern)
   - Delete `auth.py` (absorbed into `GoogleClient`)
   - `cli.py`: add `_get_client()`, update commands
   - ⚠️ `drive.py` imports `html_to_markdown` from `mail.py` — this cross-module dependency stays
   Tasks:
   - Create `GoogleClient` in `client.py`
   - Update service modules to use client._request() instead of internal _get()/get_token()
   - Update `cli.py` with `_get_client()`
   - Delete `auth.py`
   - Update tests
   Deliverable: Google integration uses `GoogleClient`, all tests pass.
   Verify: `uv run pytest tests/google/ -v` passes

5. **Brain refactor**
   Approach:
   - Create `BrainClient` in `client.py`
   - Constructor: `BrainClient(brain_dir: Path)`
   - Public methods: all current public functions, dropping the `brain_dir`/`context_path`
     first arg (derived from `self.brain_dir`)
   - Validation, config, and simple lookups stay inline in `client.py`: `validate_context`,
     `validate_origins`, `validate_name`, `list_contexts`, `configured_contexts`,
     `resolve_brain_dir`, `find_project`
   - Split heavy private implementation into modules:
     - `index.py`: `_extract_metadata`, `_parse_frontmatter`, `_indexable_items`,
       `_slug_to_name`, `_file_mtime`, reindex logic
     - `search.py`: `_match_weight`, `_rg_search`, `_rg_excerpt`, search ranking
     - `git.py`: git init, clone, commit, status operations
   - `client.py` imports from these and delegates
   - `cli.py`: add `_get_client()` that reads brain_dir from config
   - ⚠️ Functions that take `context_path` need to derive it from `self.brain_dir / context_name`
   - ⚠️ `find_project` is called from `project.py` — update that import
   - ⚠️ 101 tests — significant update, but mostly removing path args
   Tasks:
   - Create `BrainClient` class in `client.py`
   - Extract `index.py`, `search.py`, `git.py`
   - Update `cli.py` with `_get_client()`
   - Update `project.py` import
   - Update tests
   Deliverable: Brain uses `BrainClient` with split implementation modules, all tests pass.
   Verify: `uv run pytest tests/brain/ -v` passes

6. **Notion layout + full suite validation**
   Approach:
   - Reorder `notion/client.py`: public functions above `# --- Private implementation ---`
     marker, private functions below
   - No functional changes
   - Run full test suite, fix any cross-test interference
   - Document the client pattern in `CONTRIBUTING.md`
   Tasks:
   - Reorder `notion/client.py`
   - Run `uv run pytest tests/ -v`, fix any failures
   - Add "Integration Pattern" section to `CONTRIBUTING.md`
   Deliverable: All integrations follow the pattern, full suite green, pattern documented.
   Verify: `uv run pytest tests/ -v` passes, CONTRIBUTING.md updated
