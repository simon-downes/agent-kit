# Agent Kit

CLI toolkit that gives AI agents structured access to SaaS APIs. Reads credentials from environment variables, controls access via config.

## Key Rules

- Credentials come from environment variables — agent-kit does not manage authentication
- Write operations are disabled by default — enable explicitly in config
- All commands output JSON to stdout, errors to stderr
- Scope restrictions use ancestor-based checking — adding a page grants access to all descendants
- agent-kit is independent of Archie — works anywhere credentials are in env vars

## Installation

```bash
# Install from GitHub
uv tool install git+https://github.com/simon-downes/agent-kit.git

# Or install locally (editable, for development)
uv tool install -e .
```

## Configuration

Config lives at `~/.agent-kit/config.yaml`. Missing file uses safe defaults (reads enabled, writes disabled, no scope restrictions).

```yaml
notion:
  read:
    enabled: true       # default: true
    scope:
      pages: []         # page ID allowlist — empty = unrestricted
      databases: []     # database ID allowlist — empty = unrestricted
  write:
    enabled: false      # default: false
    scope:
      pages: []         # page ID allowlist — empty = unrestricted (when writes enabled)
      databases: []     # database ID allowlist — empty = unrestricted (when writes enabled)
```

### Access Scoping

Read and write operations have independent scopes. A request is allowed if the target resource ID or any of its ancestors is in the relevant allowlist — so adding a parent page automatically grants access to all its descendants.

Search is always unrestricted.

Example — read everything, write only under Platform:

```yaml
notion:
  read:
    enabled: true
    # no scope = unrestricted reads
  write:
    enabled: true
    scope:
      pages: ["15b8a35c22c380a0a284c93ef2e7bedd"]  # Platform page
```

## Notion Tool

Requires `NOTION_TOKEN` environment variable (OAuth access token). Communicates via the [Notion MCP proxy](https://developers.notion.com/docs/mcp-supported-tools).

### Read Operations

```bash
# Search the workspace (unrestricted by scope)
ak notion search "project notes"
ak notion search "roadmap" --limit 5 --type page

# Fetch a page (JSON by default)
ak notion page <page-id>
ak notion page <page-id> --markdown
ak notion page <page-id> --properties
ak notion page "https://www.notion.so/Page-Title-<id>"

# Fetch database schema
ak notion db <database-id>

# List available database views
ak notion db <database-id> --views

# Query database rows (fetches via a database view)
ak notion query <database-id>
ak notion query <database-id> --view "Overview"
ak notion query <database-id> --filter "Status=Done" --limit 10
ak notion query <database-id> --filter "Status!=Done" --filter "Owner=Platform"
ak notion query <database-id> --filter "Initiative~=GitHub"
ak notion query <database-id> --columns Initiative,Status,Owner
ak notion query <database-id> --sort "Delivery:desc"

# Fetch comments
ak notion comments <page-id>
ak notion comments <page-id> --limit 5
```

#### Query Details

`ak notion query` fetches the database to discover views, then queries via the selected view. Use `--view` to pick a view by name (defaults to the first view). Use `ak notion db <id> --views` to list available views.

Filtering (`--filter`), sorting (`--sort`), and column selection (`--columns`) are applied as post-processing on the view results. Filter operators: `=` (equals), `!=` (not equals), `~=` (contains).

### Write Operations

Disabled by default. Set `notion.operations.write: true` in config to enable.

```bash
# Create a page
ak notion create-page <parent-id> --title "New Page"
ak notion create-page <parent-id> --title "DB Entry" --prop "Status=Draft"
echo "Page content here" | ak notion create-page <parent-id> --title "With Body"

# Update page properties
ak notion update-page <page-id> --prop "Status=Complete"
ak notion update-page <page-id> --prop "Status=Done" --prop "Priority=High"

# Add a comment
ak notion comment <page-id> --message "Looks good"
echo "Detailed feedback" | ak notion comment <page-id>
```

### Output

All commands output JSON to stdout by default, parseable with `jq`:

```bash
ak notion search "test" | jq '.[0].title'
ak notion page <id> | jq .title
```

`ak notion page` supports `--markdown` for rendered content instead of JSON.

Errors go to stderr with exit codes: 0 (success), 1 (error/permission), 2 (auth failure).

## Project Structure

```
agent-kit/
├── src/agent_kit/
│   ├── cli.py                # Click CLI entry point
│   ├── config.py             # Config loading and validation
│   ├── mcp.py                # Generic MCP session context manager
│   └── notion/
│       ├── cli.py            # Notion subcommands
│       ├── client.py         # MCP tool calls, response parsing, scope checks
│       └── filters.py        # Post-processing filter parsing for query results
├── tests/
└── pyproject.toml
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and conventions.
