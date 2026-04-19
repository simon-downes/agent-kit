# Agent Kit — Jira Cloud Integration

## Objective

Add Jira Cloud issue management to agent-kit as `ak jira`. REST API v3 via httpx
(synchronous). Scoped API tokens only — authenticates via basic auth (email:token) against
`https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/...`. Covers project context, issue
CRUD, comments, and file attachments. Mirrors the Linear command structure where applicable.

## Requirements

### Credentials

- MUST require three credential fields: `email`, `token` (scoped API token), `cloud_id`
  - AC: Missing any field produces clear error with setup instructions and exit code 2
  - AC: Credentials resolved via `get_field("jira", ...)` with env var fallback
    (`JIRA_EMAIL`, `JIRA_TOKEN`, `JIRA_CLOUD_ID`)
  - Why: Scoped tokens require the cloud ID for the base URL and email+token for basic auth.
    Cloud ID is available from `https://<site>.atlassian.net/_edge/tenant_info`.

- MUST use classic scopes for minimum required permissions
  - AC: Documentation specifies `read:jira-work`, `read:jira-user`, `write:jira-work` as
    the required scopes when creating the token
  - Why: Atlassian recommends classic scopes over granular ones. These three cover all
    operations we need (read projects/issues/users, create/update issues, comments,
    attachments).

### Structure / Context

- MUST support listing projects: `ak jira projects`
  - AC: Returns JSON array of projects with id, key, name, projectTypeKey
  - AC: Supports `--limit N` (default: 50)

- MUST support project details: `ak jira project <key-or-id>`
  - AC: Returns project info including issue types and roles
  - AC: Accepts project key (e.g. "PLAT") or ID

- MUST support listing statuses for a project: `ak jira statuses <project-key>`
  - AC: Returns JSON array of statuses grouped by issue type
  - Why: Jira statuses are per-project (via workflow schemes), unlike Linear where they're
    per-team. Need a way to discover available statuses.

### Issues

- MUST support listing/filtering issues via JQL: `ak jira issues --project <key>`
  - AC: Supports `--status <name>` filter
  - AC: Supports `--assignee <name>` filter
  - AC: Supports `--type <name>` filter (issue type: Bug, Task, Story, etc.)
  - AC: Supports `--label <name>` filter
  - AC: Supports `--jql <query>` for arbitrary JQL (overrides other filters)
  - AC: Supports `--limit N` (default: 50)
  - AC: Returns JSON array with key, summary, status, assignee, priority, issuetype, labels

- MUST support fetching a single issue: `ak jira issue <key>`
  - AC: Accepts issue key (e.g. PLAT-123)
  - AC: Returns full issue detail including description, comments, labels, priority

- MUST support creating issues: `ak jira create-issue --project <key> --summary "..."`
  - AC: Supports `--type <name>` (required, e.g. "Task", "Bug", "Story")
  - AC: Supports `--description` (or stdin) — plain text, converted to ADF
  - AC: Supports `--status <name>`, `--assignee <name>`, `--priority <name>`, `--label <name>` (repeatable)
  - AC: Returns created issue JSON

- MUST support updating issues: `ak jira update-issue <key>`
  - AC: Supports `--summary`, `--description` (or stdin), `--priority <name>`, `--label <name>` (repeatable)
  - AC: Returns updated issue JSON

- MUST support transitioning issue status: `ak jira transition <key> --status <name>`
  - AC: Discovers available transitions and executes the matching one
  - Why: Jira status changes are transitions, not direct field updates. The available
    transitions depend on the workflow. This is a fundamental difference from Linear.

### Comments

- MUST support reading comments: `ak jira comments <key>`
  - AC: Returns JSON array of comments with author, body (plain text), created

- MUST support adding comments: `ak jira comment <key> --message "..."`
  - AC: Supports stdin for message body
  - AC: Returns created comment JSON

### Attachments

- MUST support attaching files to issues: `ak jira attach <key> <file-path>`
  - AC: Uploads file as an attachment on the specified issue
  - AC: Returns JSON with attachment id, filename, and content URL
  - AC: Supports any file type
  - Why: Unlike Linear's two-step upload, Jira attachments are uploaded directly to the
    issue via multipart form POST.

### General

- MUST follow existing agent-kit output conventions
  - AC: JSON to stdout, errors to stderr, exit codes 0/1/2

- MUST resolve friendly names for statuses, assignees, priorities, issue types
  - AC: `--assignee "Simon"` resolves by display name (case-insensitive partial match)
  - AC: Unresolvable names produce clear error messages listing available options

## Technical Design

### Overview

New `jira/` module following the Linear pattern. Direct REST API v3 calls via httpx
(synchronous). A `JiraClient` class handles HTTP requests with basic auth against the
scoped token endpoint. Name-to-ID resolution for statuses, assignees, issue types, and
priorities.

### Code Structure

```
src/agent_kit/jira/
├── __init__.py
├── cli.py          # Click subcommands
├── client.py       # REST client, API calls, response formatting
└── resolve.py      # Name → ID resolution (statuses, assignees, issue types, priorities)
```

### Key Decisions

- **Scoped tokens only** — base URL is `https://api.atlassian.com/ex/jira/{cloudId}`.
  Auth is HTTP basic (email:token). No support for legacy unscoped tokens or the
  `site.atlassian.net` URL format.

- **Three credential fields** — `email`, `token`, `cloud_id`. All stored in agent-kit
  credentials under the `jira` service. Cloud ID can be discovered from
  `https://<site>.atlassian.net/_edge/tenant_info` — document this in setup instructions.

- **Minimum scopes** — `read:jira-work`, `read:jira-user`, `write:jira-work`. These are
  classic (non-granular) scopes as recommended by Atlassian.

- **Synchronous httpx** — same as Linear. REST API, no streaming, no async needed.

- **JQL for search** — Jira's search is JQL-based (`/rest/api/3/search/jql`). CLI flags
  (`--project`, `--status`, `--assignee`, `--type`, `--label`) are composed into a JQL
  string. `--jql` overrides for power users.

- **Status transitions** — Jira doesn't allow direct status field updates. Status changes
  go through transitions (`GET /issue/{key}/transitions`, `POST /issue/{key}/transitions`).
  Separate `transition` command rather than a `--status` flag on `update-issue`.

- **Atlassian Document Format (ADF)** — Jira v3 API uses ADF for rich text fields
  (description, comments). For writing: accept plain text, split on newlines into
  multiple paragraph nodes (each non-empty line becomes a paragraph). For reading:
  walk the ADF tree recursively, handle `paragraph`, `heading`, `bulletList`,
  `orderedList`, `listItem`, `codeBlock`, `blockquote` node types. Extract `text`
  from leaf nodes, join paragraphs with `\n\n`, prefix headings with `#`. Ignore
  unknown node types gracefully (skip them). No markdown conversion for inline marks.

- **No pagination chasing** — use `maxResults` parameter matching `--limit`. Single page
  fetch, same as Linear.

- **Attachment upload** — direct multipart POST to `/rest/api/3/issue/{key}/attachments`
  with `X-Atlassian-Token: no-check` header. Simpler than Linear's two-step process.

- **Error handling** — `JiraClient` methods raise `ValueError` for not-found/validation
  errors. HTTP 401/403 → exit 2 (auth). All other errors → exit 1. Same pattern as Linear.
  Jira error responses contain `errorMessages` (array of strings) and `errors` (dict of
  field→message). Parse both: join `errorMessages` with "; ", append field errors as
  "field: message". Raise `ValueError` with the combined message.

- **Cross-repo changes** — agent-kit and archie are separate git repos. Commit and push
  each independently. Agent-kit changes are the primary deliverable. Archie changes
  (TOOLS.md, config, docs) are committed separately in the archie repo.

### Config Changes

No changes to agent-kit's config system. No read/write gating.

Archie changes (separate repo):
- `src/archie/config.py` DEFAULT_CONFIG: add `credentials` mapping for jira fields
- `persona/guidance/TOOLS.md`: add `ak jira` usage guidance

## Milestones

### 1. REST client and project queries

Approach:
- Create `jira/client.py` with a `JiraClient` class wrapping httpx. Constructor takes
  email, token, cloud_id. Builds base URL as
  `https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3`. Uses HTTP basic auth
  (email:token). Provides `get()`, `post()`, `put()` methods that handle JSON
  parsing and error checking.
- Credential getter needs three fields: `get_field("jira", "email")`, `token`, `cloud_id`
  with env var fallbacks `JIRA_EMAIL`, `JIRA_TOKEN`, `JIRA_CLOUD_ID`.
- Register `jira` subcommand group in main `cli.py`.
- ⚠️ Scoped tokens use `api.atlassian.com` not `site.atlassian.net`. Basic auth still
  works but the URL format is different.

Tasks:
- Create `src/agent_kit/jira/` module with `__init__.py`
- Implement `JiraClient` in `client.py` with HTTP methods and error handling
- Implement `get_projects()` — `GET /rest/api/3/project/search`
- Implement `get_project()` — `GET /rest/api/3/project/{key}` with `expand=issueTypes`
- Implement `get_statuses()` — `GET /rest/api/3/project/{key}/statuses`
- Implement CLI commands: `projects`, `project`, `statuses`
- Register `jira` group in main `cli.py`

Deliverable: `ak jira projects` returns projects, `ak jira project PLAT` returns project
details with issue types, `ak jira statuses PLAT` returns available statuses.

Verify: `ak jira projects` outputs JSON. `ak jira statuses <key>` shows workflow statuses.

### 2. Issue search and detail

Approach:
- Issue search uses `POST /rest/api/3/search/jql` with a JQL string and `fields` list.
  CLI flags compose into JQL: `project = KEY AND status = "In Progress" AND assignee = "name"`.
  `--jql` overrides the composed query entirely.
- Single issue detail uses `GET /rest/api/3/issue/{key}` with field expansion.
- ADF → plain text extraction: walk the ADF document tree recursively. Handle
  `paragraph` (join text, append `\n\n`), `heading` (prefix with `#` × level),
  `bulletList`/`orderedList`/`listItem` (prefix with `- ` or `N. `),
  `codeBlock` (wrap in backticks), `blockquote` (prefix with `> `). Extract `text`
  from leaf nodes. Skip unknown node types gracefully.
- `resolve.py` handles lookups: project statuses from the statuses endpoint, assignees
  via user search (`GET /rest/api/3/user/search?query=name`), issue types from project
  detail, priorities from `GET /rest/api/3/priority`.

Tasks:
- Implement `resolve.py` with functions to resolve assignee, issue type, priority names
- Implement `search_issues()` — JQL composition from flags + `POST /search/jql`
- Implement `get_issue()` — `GET /rest/api/3/issue/{key}` with ADF text extraction
- Implement ADF → plain text helper
- Implement CLI commands: `issues`, `issue`

Deliverable: `ak jira issues --project PLAT --status "In Progress"` returns filtered
issues. `ak jira issue PLAT-123` returns full issue detail with plain text description.

Verify: Both commands return valid JSON. Status filtering works. Description is readable
plain text.

### 3. Issue create, update, and transition

Approach:
- Create uses `POST /rest/api/3/issue` with fields dict. Description is plain text
  converted to ADF: split on `\n\n` (or `\n`) into paragraphs, each becomes a
  `{"type": "paragraph", "content": [{"type": "text", "text": "..."}]}` node in the
  ADF doc. Empty lines are skipped.
- Update uses `PUT /rest/api/3/issue/{key}` with fields dict. Same ADF wrapping for
  description.
- Transition uses `GET /rest/api/3/issue/{key}/transitions` to discover available
  transitions, matches by name (case-insensitive), then `POST /rest/api/3/issue/{key}/transitions`
  with the transition ID.
- ⚠️ Issue type is required for creation. Priority names need resolution via
  `GET /rest/api/3/priority`.
- ⚠️ Labels are plain strings in Jira (not IDs) — pass through directly.

Tasks:
- Implement plain text → ADF helper
- Implement `create_issue()` with field resolution
- Implement `update_issue()` with field resolution
- Implement `transition_issue()` — discover + execute transition
- Implement CLI commands: `create-issue`, `update-issue`, `transition`

Deliverable: Issues can be created, updated, and transitioned via CLI with friendly names.

Verify: Create an issue, verify it appears in Jira. Transition its status, verify the change.

### 4. Comments and attachments

Approach:
- Comments: `GET /rest/api/3/issue/{key}/comment` for reading (extract plain text from
  ADF body), `POST /rest/api/3/issue/{key}/comment` for adding (wrap plain text in ADF).
- Attachments: `POST /rest/api/3/issue/{key}/attachments` with multipart form data.
  Requires `X-Atlassian-Token: no-check` header to bypass XSRF check.
  The `write:jira-work` scope covers attachment uploads.
- Comment body from `--message` or stdin, same pattern as Linear.

Tasks:
- Implement `get_comments()` with ADF → text extraction
- Implement `create_comment()` with text → ADF wrapping
- Implement `attach_file()` — multipart upload
- Implement CLI commands: `comments`, `comment`, `attach`

Deliverable: Comments can be read and added. Files can be attached to issues.

Verify: Read comments on an issue. Add a comment. Attach a file, verify it appears in Jira.

### 5. Documentation and Archie integration

Approach:
- Agent-kit docs follow the pattern of existing `docs/linear.md` — full command reference
  with examples. Setup instructions must cover: creating a scoped API token with the three
  required classic scopes, obtaining the cloud ID from `_edge/tenant_info`, and storing
  credentials via `ak auth set`.
- Archie changes are in the separate archie repo at the parent directory. Commit separately.
- `tool-issues` skill at `persona/skills/tool-issues/` has a provider dispatch pattern.
  Add `references/provider-jira.md` following the structure of `provider-linear.md`.

Tasks:
- Create `docs/jira.md` with full command reference and setup instructions
- Update agent-kit `README.md` with Jira command summary
- Add `ak jira` section to Archie's `persona/guidance/TOOLS.md`
- Add Jira credential mappings to Archie's `src/archie/config.py` DEFAULT_CONFIG
- Update Archie's `docs/getting-started.md` with Jira credential setup
- Add `references/provider-jira.md` to Archie's `persona/skills/tool-issues/`

Deliverable: Documentation covers all Jira commands with examples and setup instructions.

Verify: README has Jira section. `docs/jira.md` has complete command reference. Getting
started guide includes Jira setup.
