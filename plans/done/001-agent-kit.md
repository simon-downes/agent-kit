# Agent Kit — CLI Toolkit for AI Agent Capabilities

## Objective

Build a standalone CLI toolkit (`ak`) that gives AI agents structured access to SaaS APIs.
The first integration is Notion, accessed via the Notion MCP proxy server. Credentials are
read from environment variables (injected by Archie, but agent-kit has no dependency on Archie).
A config file controls access scoping — which operations are allowed and which resources are
accessible — so agents can be given limited, predictable access to external services.

## Requirements

### Core

- MUST be a standalone Python CLI package installable via `uv tool install`
  - AC: `uv tool install .` succeeds and `ak --help` shows available commands

- MUST read credentials from environment variables, not manage authentication
  - AC: Notion commands use `NOTION_TOKEN` env var for the OAuth access token
  - AC: Missing token produces a clear error message and exit code 2

- MUST load configuration from `~/.agent-kit/config.yaml`
  - AC: Config file is loaded on startup if it exists
  - AC: Missing config file uses sensible defaults (reads enabled, writes disabled)
  - AC: Invalid config produces a clear error message to stderr and exit code 1

- MUST gate operations by category (read/write) via config
  - AC: Write operations are disabled by default
  - AC: Attempting a disabled operation produces a clear error and exit code 1
  - AC: Enabling writes in config allows write operations to execute

### Notion Tool

#### Read Operations

- MUST support searching the workspace: `ak notion search <query>`
  - AC: Returns matching pages/databases as JSON array to stdout
  - AC: Supports `--limit N` to cap results (default: 10)
  - AC: Supports `--type page|database` to filter result type

- MUST support fetching page content: `ak notion page <id-or-url>`
  - AC: Returns page content as JSON by default (consistent with all other commands)
  - AC: Supports `--markdown` flag for rendered markdown output
  - AC: Supports `--properties` flag to include page property metadata in output

- MUST support fetching database schema: `ak notion db <id-or-url>`
  - AC: Returns database properties/schema as JSON

- MUST support querying database rows: `ak notion query <id-or-url>`
  - AC: Returns rows as JSON array of objects
  - AC: Supports `--filter Key=Value` (repeatable) for simplified filtering
  - AC: Supports `--filter-raw '<json>'` for native Notion filter passthrough
  - AC: Supports `--sort property:asc|desc`
  - AC: Supports `--columns col1,col2,col3` to select specific properties
  - AC: Supports `--limit N` to cap results

- MUST support fetching comments: `ak notion comments <id-or-url>`
  - AC: Returns comments as JSON array
  - AC: Supports `--limit N` to cap results

#### Write Operations (config-gated, disabled by default)

- MUST support creating pages: `ak notion create-page <parent-id>`
  - AC: Supports `--title "..."` for page title
  - AC: Supports `--prop Key=Value` (repeatable) for database row properties
  - AC: Accepts body content from stdin

- MUST support updating page properties: `ak notion update-page <id>`
  - AC: Supports `--prop Key=Value` (repeatable) for property updates

- MUST support adding comments: `ak notion comment <id>`
  - AC: Supports `--message "..."` or stdin for comment body

#### Access Scoping

- SHOULD support restricting access to specific pages or databases via config
  - AC: Config `scope.pages` is an allowlist of page IDs — page fetch/comments are
    rejected for IDs not in the list
  - AC: Config `scope.databases` is an allowlist of database IDs — db/query operations
    are rejected for IDs not in the list
  - AC: Search results are post-filtered to only include pages/databases in scope
  - AC: Empty scope lists mean unrestricted access (default)
  - Why: Subtree-based restriction (pages under a root) requires parent chain traversal
    and is deferred. ID allowlists are the initial implementation.

### Output

- MUST output JSON to stdout by default for all commands
  - AC: Output is valid JSON parseable by `jq`
  - AC: `ak notion page` supports `--markdown` flag for rendered content

- MUST output errors to stderr
  - AC: Error messages are human-readable plain text (no colour codes)
  - AC: Exit codes: 0 success, 1 error/permission, 2 auth failure

### Non-Functional

- MUST follow the same code style conventions as Archie (ruff, line length 100, Python 3.11+)
  - AC: `ruff check src/` and `ruff format --check src/` pass clean

- SHOULD keep the MCP connection layer generic enough to support future MCP-based tools
  - AC: MCP session management is not Notion-specific

## Technical Design

### Overview

A Python CLI package using Click for commands and the `mcp` library for Notion MCP server
communication. Each service (starting with Notion) is a subcommand group. A thin config
layer controls access permissions and scoping. The MCP connection is managed as a reusable
async context manager.

### Technical Stack

- **Python 3.11+** — matches Archie's target (the old agent-kit targeted 3.13, this is a
  deliberate broadening for compatibility)
- **click** — CLI framework (consistent with Archie)
- **mcp>=1.0.0** — MCP client library for Notion proxy communication. Uses
  `mcp.client.streamable_http.streamablehttp_client` for HTTP-based MCP transport.
- **httpx** — HTTP client (mcp dependency, also available for future direct-API tools)
- **pyyaml** — config file parsing
- **hatchling** — build backend (consistent with Archie)
- **ruff** — linting and formatting only (no black, no mypy — consistent with Archie)

No `rich` dependency. Archie uses rich for its interactive terminal UI, but agent-kit's
primary consumers are agents — output is JSON, errors are plain text to stderr.

### Architecture

```
Environment (NOTION_TOKEN, etc.)
        │
        ▼
   ┌─────────┐     ┌──────────────┐     ┌─────────────────────┐
   │  CLI     │────▶│  Config      │     │  MCP Session        │
   │  (Click) │     │  (YAML)      │     │  (async ctx mgr)    │
   └────┬─────┘     └──────────────┘     └──────────┬──────────┘
        │                                           │
        ▼                                           ▼
   ┌─────────────┐                          ┌───────────────┐
   │  Notion     │─── permission check ────▶│  Notion MCP   │
   │  Commands   │─── scope check ─────────▶│  Server       │
   │             │─── MCP tool call ───────▶│  (remote)     │
   └─────────────┘                          └───────────────┘
```

### Code Structure

```
agent-kit/
├── src/agent_kit/
│   ├── __init__.py           # Package version
│   ├── cli.py                # Click group, top-level entry point
│   ├── config.py             # Config loading, defaults, validation
│   ├── mcp.py                # Generic MCP session async context manager
│   └── notion/
│       ├── __init__.py
│       ├── cli.py            # Notion subcommands (Click commands)
│       ├── client.py         # Notion MCP tool calls, response parsing, scope checks
│       └── filters.py        # Simplified filter syntax → Notion filter JSON
├── tests/
├── pyproject.toml
└── README.md
```

### Patterns and Conventions

- **Config**: YAML file at `~/.agent-kit/config.yaml`, loaded once at CLI startup via a
  `@dataclass` (`Config`) with nested dataclasses for service config. Missing file → defaults.
  Invalid file → error to stderr, exit 1.
- **Error handling**: errors print to stderr via `print(..., file=sys.stderr)` and exit with
  appropriate code. No exceptions leak to the user. Auth errors (missing token, 401) → exit 2.
  Permission/config errors → exit 1. MCP connection failures (timeout, server unavailable) →
  print actionable message to stderr, exit 1. Rate limiting (429) → print retry guidance, exit 1.
- **Async**: MCP requires async. CLI commands use `asyncio.run()` to bridge sync Click → async
  MCP calls. The MCP session is an `async with` context manager — no manual `__aexit__` calls.
- **Output**: all commands write JSON to stdout via `json.dumps()`. `--markdown` flag on page
  fetch writes markdown to stdout instead. Errors always to stderr via `print(file=sys.stderr)`.
- **Constants**: Notion MCP URL (`https://mcp.notion.com/mcp`) is a constant in
  `notion/client.py`. Not configurable initially — can be promoted to config if needed.

### Config Schema

```yaml
notion:
  operations:
    read: true       # default: true
    write: false     # default: false
  scope:
    pages: []        # page ID allowlist — empty = unrestricted
    databases: []    # database ID allowlist — empty = unrestricted
```

### Key Decisions

- **MCP proxy over REST API for Notion**: the Notion REST API requires workspace integrations
  which aren't enabled/scalable for multi-user OAuth. The MCP proxy accepts OAuth tokens
  directly and handles API translation.
- **No rich/colour output**: primary consumers are agents, not humans. JSON is the default.
  Keeps dependencies minimal.
- **Config-gated writes over separate commands**: all commands exist in code, gated by config
  check. Simpler than conditional command registration and gives clear error messages.
- **Simplified filter syntax**: `--filter Key=Value` covers 80% of database query use cases
  without requiring agents to construct Notion's verbose filter JSON. `--filter-raw` is the
  escape hatch.
- **Generic MCP module**: the `mcp.py` module handles session lifecycle without Notion-specific
  logic, so future MCP-based tools (if any) can reuse it.
- **ID allowlist over subtree scoping**: subtree restriction requires parent chain traversal
  (multiple API calls per request). ID allowlists are simple, predictable, and sufficient for
  initial use. Subtree scoping can be added later.
- **Discover MCP tools at runtime**: the Notion MCP server's tool names and parameters should
  be verified via `session.list_tools()` during development. Tool names referenced in this plan
  are based on Notion's documentation but must be confirmed against the live server.

## Testing Constraint

All manual verification of read and write operations during implementation MUST be directed
at the designated test page:

- URL: https://www.notion.so/Agent-Kit-Test-3308a35c22c380ccb0a8fe567b6faca5
- Page ID: `3308a35c22c380ccb0a8fe567b6faca5`

Do not read from or write to any other Notion pages during development and testing.

## Milestones

### 1. Project scaffold and config system

Approach:
- Use hatchling build backend, same pyproject.toml structure as Archie
- Config module loads YAML, merges with defaults, validates structure
- Use `@dataclass` for config types: `Config` → `NotionConfig` → `OperationsConfig`, `ScopeConfig`
- ⚠️ Config path `~/.agent-kit/config.yaml` must expand `~` via `Path.expanduser()`

Tasks:
- Create project directory structure and `pyproject.toml` with dependencies
- Implement `config.py` with default config, YAML loading, validation, and config dataclasses
- Implement `cli.py` with top-level Click group and `--version` flag
- Register `notion` as an empty subcommand group

Deliverable: `ak --help` shows the CLI with a `notion` subcommand group, config loads from
`~/.agent-kit/config.yaml` with defaults when missing.

Verify: `uv run ak --help` shows help text with `notion` listed. `uv run ak notion --help`
shows the notion subgroup. Creating a config file with `notion.operations.write: true` is
loaded correctly.

### 2. MCP connection layer and page fetch

Approach:
- MCP session as `async with` context manager in `mcp.py` — takes URL and headers dict,
  returns initialised `ClientSession`. Uses `streamablehttp_client` from `mcp.client.streamable_http`.
- First task: connect to the Notion MCP server and call `session.list_tools()` to discover
  actual tool names and parameters. Document findings and adjust subsequent implementation.
- Notion client in `notion/client.py` wraps MCP tool calls with response parsing
- The `notion-fetch` MCP tool accepts an `id` parameter (page ID or URL) based on old code
  and Notion docs — verify via tool discovery
- Env var: `NOTION_TOKEN` — check at command entry, print error to stderr and exit 2 if missing
- ⚠️ MCP connection errors (timeout, DNS, server 5xx) must be caught and reported as
  actionable messages to stderr, not raw tracebacks

Tasks:
- Implement `mcp.py` with generic async context manager for MCP sessions
- Connect to Notion MCP server and enumerate available tools via `session.list_tools()`,
  document the actual tool names and parameter schemas
- Implement `notion/client.py` with `fetch_page()` method and response parsing
- Implement `ak notion page <id>` command with `--json`, `--markdown`, and `--properties` flags
- Add config check for read permission before executing

Deliverable: `ak notion page <page-id>` fetches and outputs a Notion page as JSON (default)
or markdown (`--markdown`).

Verify: `NOTION_TOKEN=<token> uv run ak notion page <known-page-id>` outputs page content
as JSON. Adding `--markdown` outputs markdown. Running without `NOTION_TOKEN` exits with
code 2 and a clear error message.

### 3. Search and database operations

Approach:
- Use tool names and parameters discovered in milestone 2
- `notion-search` takes a `query` parameter (per old code and docs)
- Database schema: `notion-fetch` with a database ID returns schema info
- Database querying: use whichever query tool was discovered in milestone 2. If the MCP
  server provides a dedicated query tool, use it. Otherwise, `notion-fetch` on the database
  and post-process.
- Simplified filters in `notion/filters.py`: parse `Key=Value` strings into the filter
  format expected by the MCP tool. Default to text `equals` comparison. Support `!=` for
  `does_not_equal`. `--filter-raw` passes JSON directly to the MCP tool.
- Column selection: post-process the MCP response to include only requested property keys

Tasks:
- Implement `ak notion search <query>` with `--limit` and `--type` options
- Implement `ak notion db <id>` for database schema fetch
- Implement `notion/filters.py` with simplified filter parsing
- Implement `ak notion query <id>` with `--filter`, `--filter-raw`, `--sort`, `--columns`,
  `--limit` options
- Implement `ak notion comments <id>` with `--limit` option

Deliverable: All read commands work — search, page, db, query, comments — with filtering
and column selection on database queries.

Verify: `ak notion search "test"` returns JSON results. `ak notion query <db-id> --filter
"Status=Done" --columns Title,Status --limit 5` returns filtered, column-selected JSON.

### 4. Write operations (config-gated)

Approach:
- Write commands check `config.notion.operations.write` before executing — use a shared
  helper function that prints error to stderr and exits 1 if writes are disabled
- Use MCP tool names discovered in milestone 2 for create/update/comment operations
- Stdin reading for body content: `sys.stdin.read()` if `not sys.stdin.isatty()`, skip otherwise
- `--prop Key=Value` parsing: split on first `=` only (values may contain `=`)

Tasks:
- Implement write permission check helper
- Implement `ak notion create-page <parent-id>` with `--title`, `--prop`, stdin body
- Implement `ak notion update-page <id>` with `--prop`
- Implement `ak notion comment <id>` with `--message` / stdin

Deliverable: Write commands execute when enabled in config, reject with clear error when
disabled.

Verify: With default config (writes disabled), `ak notion create-page <id> --title "test"`
exits with error message and code 1. With `write: true` in config, the command creates a
page and outputs the result as JSON.

### 5. Access scoping

Approach:
- Scope enforcement in `notion/client.py` as pre-flight checks before MCP calls
- `scope.databases`: reject db/query operations if target ID is not in the allowlist
- `scope.pages`: reject page/comments operations if target ID is not in the allowlist
- Search results: post-filter to remove results whose IDs aren't in either allowlist
- Empty lists = unrestricted (no filtering)
- ⚠️ Scope enforcement on search is best-effort — the MCP server still sees the query,
  we just filter the results. Document this limitation.

Tasks:
- Implement scope checking functions in `notion/client.py`
- Add database ID validation to db and query commands
- Add page ID validation to page and comments commands
- Add scope filtering to search results
- Document scoping behaviour and limitations in README

Deliverable: Operations on resources outside configured scope are rejected or filtered out.

Verify: Configure `scope.databases: ["<db-id>"]`, attempt to query a different database —
rejected with error. Search results only include items matching scope. Empty scope lists
allow everything.

### 6. Documentation and packaging

Approach:
- README with installation, configuration, command reference, examples
- Follow Archie's pyproject.toml patterns for build config
- Ensure `uv tool install .` works cleanly from the `agent-kit/` directory

Tasks:
- Write README.md with full command reference and config documentation
- Write CONTRIBUTING.md with development setup and conventions
- Verify `uv tool install .` works
- Final `ruff check` and `ruff format` pass

Deliverable: Package installs cleanly and documentation covers all commands and configuration.

Verify: `uv tool install .` succeeds from the `agent-kit/` directory. `ak --help` works.
README covers all commands with examples.
