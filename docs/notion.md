# Notion

Search, fetch, and manage Notion content via the
[Notion MCP proxy](https://developers.notion.com/docs/mcp-supported-tools).

## Credentials

Requires a Notion OAuth token. Resolved in order:

1. `~/.agent-kit/credentials.yaml` → `notion.access_token`
2. `NOTION_TOKEN` environment variable

```bash
ak auth login notion
```

## Configuration

```yaml
notion:
  read:
    enabled: true         # default: true
    scope:
      pages: []           # page ID allowlist — empty = unrestricted
      databases: []       # database ID allowlist — empty = unrestricted
  write:
    enabled: false        # default: false
    scope:
      pages: []
      databases: []
```

Read and write have independent scopes. A request is allowed if the target resource ID or
any of its ancestors is in the relevant allowlist — adding a parent page grants access to
all descendants. Search is always unrestricted.

## Read Commands

### `ak notion search <query>`

Search the Notion workspace. Unrestricted by scope.

```bash
ak notion search "project notes"
ak notion search "roadmap" --limit 5 --type page
```

| Option | Description |
|--------|-------------|
| `--limit N` | Maximum results (default: 10) |
| `--type page\|database` | Filter by resource type |

### `ak notion page <id-or-url>`

Fetch a Notion page by ID or URL.

```bash
ak notion page <page-id>
ak notion page <page-id> --markdown
ak notion page <page-id> --properties
ak notion page "https://www.notion.so/Page-Title-<id>"
```

| Option | Description |
|--------|-------------|
| `--markdown` | Output rendered content as markdown instead of JSON |
| `--properties` | Include page properties in JSON output |

### `ak notion db <id-or-url>`

Fetch a database schema.

```bash
ak notion db <database-id>
ak notion db <database-id> --views
```

| Option | Description |
|--------|-------------|
| `--views` | List available view names instead of full schema |

### `ak notion query <id-or-url>`

Query database rows via a view, with optional post-processing.

```bash
ak notion query <database-id>
ak notion query <database-id> --view "Overview"
ak notion query <database-id> --filter "Status=Done" --limit 10
ak notion query <database-id> --filter "Status!=Done" --filter "Owner=Platform"
ak notion query <database-id> --filter "Initiative~=GitHub"
ak notion query <database-id> --columns Initiative,Status,Owner
ak notion query <database-id> --sort "Delivery:desc"
```

| Option | Description |
|--------|-------------|
| `--view NAME` | View name to query (default: first view) |
| `--filter EXPR` | Post-processing filter (repeatable) |
| `--sort PROP:dir` | Sort by property, `asc` or `desc` |
| `--columns A,B,C` | Comma-separated properties to include |
| `--limit N` | Maximum results |

Filter operators: `=` (equals), `!=` (not equals), `~=` (contains).

Use `ak notion db <id> --views` to discover available view names.

### `ak notion comments <id-or-url>`

Fetch comments on a page.

```bash
ak notion comments <page-id>
ak notion comments <page-id> --limit 5
```

## Write Commands

Disabled by default. Set `notion.write.enabled: true` in config.

### `ak notion create-page <parent-id>`

Create a page under a parent.

```bash
ak notion create-page <parent-id> --title "New Page"
ak notion create-page <parent-id> --title "DB Entry" --prop "Status=Draft"
echo "Page content" | ak notion create-page <parent-id> --title "With Body"
```

| Option | Description |
|--------|-------------|
| `--title TEXT` | Page title |
| `--prop KEY=VALUE` | Set a property (repeatable) |
| stdin | Page body content |

### `ak notion update-page <id-or-url>`

Update page properties.

```bash
ak notion update-page <page-id> --prop "Status=Complete"
ak notion update-page <page-id> --prop "Status=Done" --prop "Priority=High"
```

### `ak notion comment <id-or-url>`

Add a comment to a page.

```bash
ak notion comment <page-id> --message "Looks good"
echo "Detailed feedback" | ak notion comment <page-id>
```

## Access Scoping

Scope checks happen after fetching — the MCP response includes ancestor data used for
validation. If a resource or any of its ancestors is in the allowlist, access is granted.

Example — read everything, write only under a specific page:

```yaml
notion:
  read:
    enabled: true
  write:
    enabled: true
    scope:
      pages: ["15b8a35c22c380a0a284c93ef2e7bedd"]
```
