# Jira

Issue tracking and project management via Jira Cloud REST API v3. Uses scoped API tokens
with Basic auth (email:token) against `api.atlassian.com`.

## Credentials

Requires three credential fields. Resolved in order:

1. `~/.agent-kit/credentials.yaml` → `jira.email`, `jira.token`, `jira.cloud_id`
2. `JIRA_EMAIL`, `JIRA_TOKEN`, `JIRA_CLOUD_ID` environment variables

```bash
ak auth set jira email
ak auth set jira token
ak auth set jira cloud_id
```

### Setup

1. **Create a scoped API token** at https://id.atlassian.com/manage-profile/security/api-tokens
   - Click "Create API token with scopes"
   - Add these classic scopes: `read:jira-work`, `read:jira-user`, `write:jira-work`
   - Set an expiry (max 365 days)

2. **Get your cloud ID** — visit `https://<your-site>.atlassian.net/_edge/tenant_info`
   and copy the `cloudId` value.

3. **Store credentials:**
   ```bash
   ak auth set jira email      # your Atlassian account email
   ak auth set jira token      # the scoped API token
   ak auth set jira cloud_id   # the cloud ID from step 2
   ```

## Commands

### `ak jira projects`

List projects.

```bash
ak jira projects
ak jira projects --limit 10
```

| Option | Description |
|--------|-------------|
| `--limit N` | Maximum results (default: 50) |

### `ak jira project <key-or-id>`

Get project details including issue types.

```bash
ak jira project PLAT
```

### `ak jira statuses <project-key>`

List statuses for a project, grouped by issue type. Use this to discover available
statuses before filtering or transitioning issues.

```bash
ak jira statuses PLAT
```

### `ak jira issues`

Search issues with filters. Filters are composed into JQL. Use `--jql` for complex queries.

```bash
ak jira issues --project PLAT
ak jira issues --project PLAT --status "In Progress" --limit 10
ak jira issues --project PLAT --assignee "Simon" --type "Bug"
ak jira issues --jql 'project = PLAT AND sprint in openSprints()'
```

| Option | Description |
|--------|-------------|
| `--project KEY` | Filter by project key |
| `--status NAME` | Filter by status name |
| `--assignee NAME` | Filter by assignee name |
| `--type NAME` | Filter by issue type (Bug, Task, Story, etc.) |
| `--label NAME` | Filter by label |
| `--jql QUERY` | Raw JQL (overrides other filters) |
| `--limit N` | Maximum results (default: 50) |

### `ak jira issue <key>`

Get full issue details including description, comments, and project.

```bash
ak jira issue PLAT-123
```

### `ak jira create-issue`

Create a new issue.

```bash
ak jira create-issue --project PLAT --summary "Fix auth bug" --type Task
ak jira create-issue --project PLAT --summary "New feature" --type Story --priority High
echo "Long description" | ak jira create-issue --project PLAT --summary "From stdin" --type Task
```

| Option | Description |
|--------|-------------|
| `--project KEY` | Project key (required) |
| `--summary TEXT` | Issue summary (required) |
| `--type NAME` | Issue type: Bug, Task, Story, etc. (required) |
| `--description TEXT` | Description (or pipe via stdin) |
| `--priority NAME` | Priority name (e.g. High, Medium, Low) |
| `--assignee NAME` | Assignee name (partial match) |
| `--label NAME` | Label (repeatable) |

### `ak jira update-issue <key>`

Update an issue.

```bash
ak jira update-issue PLAT-123 --summary "Updated title"
ak jira update-issue PLAT-123 --priority High --assignee "Simon"
ak jira update-issue PLAT-123 --label "Bug" --label "Urgent"
```

| Option | Description |
|--------|-------------|
| `--summary TEXT` | New summary |
| `--description TEXT` | New description (or pipe via stdin) |
| `--priority NAME` | Priority name |
| `--assignee NAME` | Assignee name |
| `--label NAME` | Label (repeatable, replaces all) |

### `ak jira transition <key>`

Transition an issue to a new status. Discovers available transitions from the issue's
current workflow state.

```bash
ak jira transition PLAT-123 --status "In Progress"
ak jira transition PLAT-123 --status "Done"
```

| Option | Description |
|--------|-------------|
| `--status NAME` | Target status name (required) |

**Note:** Available transitions depend on the issue's current status and workflow. Use
`ak jira statuses <project>` to see all possible statuses.

### `ak jira comments <key>`

List comments on an issue.

```bash
ak jira comments PLAT-123
```

### `ak jira comment <key>`

Add a comment to an issue.

```bash
ak jira comment PLAT-123 --message "Looks good"
echo "Detailed feedback" | ak jira comment PLAT-123
```

### `ak jira attach <key> <file-path>`

Attach a file to an issue.

```bash
ak jira attach PLAT-123 ./screenshot.png
ak jira attach PLAT-123 ./report.pdf
```
