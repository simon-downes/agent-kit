# Agent Kit

CLI toolkit that gives AI agents structured access to SaaS APIs. Designed for LLM agents
as the primary consumer — structured output by default, token-efficient, composable with
shell pipelines.

## Installation

```bash
uv tool install git+https://github.com/simon-downes/agent-kit.git
```

## Getting Started

### 1. Add credentials

```bash
# Static tokens — prompted interactively
ak auth set github token
ak auth set linear token
ak auth set slack webhook_url

# OAuth services — opens browser
ak auth login notion

# Import from environment (e.g. via aws-vault)
aws-vault exec my-profile -- ak auth import aws \
  AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
```

Credentials are stored in `~/.agent-kit/credentials.yaml` (mode 0600).

### 2. Configure (optional)

Config lives at `~/.agent-kit/config.yaml`. Missing file uses safe defaults. The main
thing you might configure is Notion access scoping:

```yaml
notion:
  write:
    enabled: true
    scope:
      pages: ["<page-id>"]   # restrict writes to this subtree
```

### 3. Use

```bash
ak notion search "project notes"
ak linear issues --team PLAT --status "In Progress"
ak slack send "Deploy complete :white_check_mark:"
```

## Tools

### [Auth](docs/auth.md)

Credential management — store tokens, OAuth login, import from environment.

### [Brain](docs/brain.md)

Query and manage the second brain — ranked multi-term search, indexing, reference
creation, status, validation.

### [Notion](docs/notion.md)

Search, fetch pages/databases, query database views, create/update pages, add comments.
Communicates via the Notion MCP proxy. Supports read/write scoping.

### [Linear](docs/linear.md)

Issue tracking — list teams/projects, query issues, create/update issues, comments, file
uploads. Communicates directly with Linear's GraphQL API.

### [Jira](docs/jira.md)

Issue tracking — list projects, query issues via JQL, create/update/transition issues,
comments, file attachments. Communicates with Jira Cloud REST API v3 using scoped API tokens.

### [Google Workspace](docs/google.md)

Read-only access to Gmail, Calendar, and Google Drive. Search and read emails, list
events, search and fetch documents. Google Docs export as markdown via pandoc.

### [Slack](docs/slack.md)

Read channels, search messages, list users, and send notifications. Read via user
token OAuth, write via incoming webhooks.

## Output Conventions

- **stdout** — structured data (JSON by default), or plain text for simple confirmations
- **stderr** — error messages, progress indicators
- **exit codes** — 0 success, 1 error, 2 auth failure

All JSON output is parseable with `jq`:

```bash
ak notion search "test" | jq '.[0].title'
ak linear issues --team PLAT | jq '.[].identifier'
```

## Documentation

- [Auth](docs/auth.md) — credential management
- [Brain](docs/brain.md) — second brain management
- [Notion](docs/notion.md) — Notion integration
- [Linear](docs/linear.md) — Linear integration
- [Jira](docs/jira.md) — Jira Cloud integration
- [Google Workspace](docs/google.md) — Gmail, Calendar, and Drive
- [Slack](docs/slack.md) — Slack integration
- [CONTRIBUTING.md](CONTRIBUTING.md) — development setup and conventions
