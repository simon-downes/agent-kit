# Linear

Issue tracking and project management via Linear's GraphQL API.

## Credentials

Requires a Linear personal API key. Resolved in order:

1. `~/.agent-kit/credentials.yaml` → `linear.token`
2. `LINEAR_TOKEN` environment variable

```bash
ak auth set linear token
```

## Commands

### `ak linear teams`

List all teams.

### `ak linear team <id-or-key>`

Get team details including workflow states, labels, and members. Accepts team ID or key
(e.g. `PLAT`).

```bash
ak linear team PLAT
```

Use this to discover available statuses, labels, and members before filtering or creating
issues.

### `ak linear projects`

List projects.

```bash
ak linear projects
ak linear projects --team PLAT
```

| Option | Description |
|--------|-------------|
| `--team KEY` | Filter by team key |

### `ak linear issues`

List issues with server-side filtering. Filters use friendly names — statuses, assignees,
and labels are resolved to IDs automatically.

```bash
ak linear issues --team PLAT
ak linear issues --team PLAT --status "In Progress" --limit 10
ak linear issues --team PLAT --assignee "Simon" --label "Bug"
ak linear issues --team PLAT --project "Q1 Roadmap"
```

| Option | Description |
|--------|-------------|
| `--team KEY` | Team key (required) |
| `--status NAME` | Filter by status name |
| `--assignee NAME` | Filter by assignee name (partial match) |
| `--label NAME` | Filter by label name |
| `--project NAME` | Filter by project name |
| `--limit N` | Maximum results (default: 50) |

### `ak linear issue <identifier>`

Get full issue details including description, comments, and team.

```bash
ak linear issue PLAT-123
```

### `ak linear create-issue`

Create a new issue.

```bash
ak linear create-issue --team PLAT --title "Fix auth bug"
ak linear create-issue --team PLAT --title "New feature" --status "Ready" --priority 2
ak linear create-issue --team PLAT --title "With description" --description "Details here"
echo "Long description" | ak linear create-issue --team PLAT --title "From stdin"
```

| Option | Description |
|--------|-------------|
| `--team KEY` | Team key (required) |
| `--title TEXT` | Issue title (required) |
| `--description TEXT` | Description (or pipe via stdin) |
| `--status NAME` | Status name |
| `--assignee NAME` | Assignee name |
| `--priority 1-4` | Priority: 1 urgent, 2 high, 3 medium, 4 low |
| `--label NAME` | Label name (repeatable) |

### `ak linear update-issue <identifier>`

Update an issue. Resolves names to IDs using the issue's team context.

```bash
ak linear update-issue PLAT-123 --status "Done"
ak linear update-issue PLAT-123 --assignee "Simon" --priority 1
ak linear update-issue PLAT-123 --label "Bug" --label "Urgent"
```

Same options as `create-issue` (except `--team` and `--title`).

### `ak linear comments <identifier>`

List comments on an issue.

```bash
ak linear comments PLAT-123
```

### `ak linear comment <identifier>`

Add a comment to an issue.

```bash
ak linear comment PLAT-123 --message "Looks good"
echo "Detailed feedback" | ak linear comment PLAT-123
```

### `ak linear upload <file-path>`

Upload a file to Linear's storage. Returns an asset URL for embedding in descriptions or
comments.

```bash
ak linear upload ./screenshot.png
```

Use the returned `assetUrl` in markdown: `![screenshot](asset-url)` for images,
`[filename](asset-url)` for other files.
