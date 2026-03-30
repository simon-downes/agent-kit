# Agent Kit — Linear Integration

## Objective

Add Linear issue management to agent-kit as `ak linear`. Direct GraphQL API calls via httpx
(no MCP). Covers team/project context, issue CRUD, and comments. Uses friendly names for
statuses, assignees, and labels — resolves to IDs internally. Auth via `LINEAR_API_KEY` env var.

## Requirements

### Structure / Context

- MUST support listing teams: `ak linear teams`
  - AC: Returns JSON array of teams with id, name, key

- MUST support team details with workflow states: `ak linear team <id-or-key>`
  - AC: Returns team info including workflow states (statuses) with names and types
  - AC: Accepts team key (e.g. "PLAT") or UUID

- MUST support listing projects: `ak linear projects [--team <key>]`
  - AC: Returns JSON array of projects with id, name, state
  - AC: Optional team filter

### Issues

- MUST support listing/filtering issues: `ak linear issues --team <key>`
  - AC: Supports `--status <name>` filter
  - AC: Supports `--assignee <name>` filter
  - AC: Supports `--label <name>` filter
  - AC: Supports `--project <name>` filter
  - AC: Supports `--limit N` (default: 50)
  - AC: Returns JSON array with id, identifier, title, status, assignee, priority, labels

- MUST support fetching a single issue: `ak linear issue <identifier>`
  - AC: Accepts shorthand (PLAT-123) or UUID
  - AC: Returns full issue detail including description, comments count, project, labels

- MUST support creating issues: `ak linear create-issue --team <key> --title "..."`
  - AC: Supports `--description` (or stdin)
  - AC: Supports `--status <name>`, `--assignee <name>`, `--priority <1-4>`, `--label <name>` (repeatable)
  - AC: Returns created issue JSON

- MUST support updating issues: `ak linear update-issue <identifier>`
  - AC: Supports `--status <name>`, `--assignee <name>`, `--priority <1-4>`, `--title "..."`
  - AC: Supports `--label <name>` (repeatable, replaces all labels)
  - AC: Returns updated issue JSON

### Attachments

- MUST support uploading files: `ak linear upload <file-path>`
  - AC: Uploads file to Linear's cloud storage via `fileUpload` mutation + PUT
  - AC: Returns JSON with the asset URL
  - AC: Supports any file type
  - Why: The returned URL can be embedded in issue descriptions or comments as
    markdown (`![alt](url)` for images, `[name](url)` for other files)

### Comments

- MUST support reading comments: `ak linear comments <identifier>`
  - AC: Returns JSON array of comments with author, body, createdAt

- MUST support adding comments: `ak linear comment <identifier> --message "..."`
  - AC: Supports stdin for message body
  - AC: Returns created comment JSON

### General

- MUST use `LINEAR_API_KEY` env var for authentication
  - AC: Missing key produces clear error and exit code 2

- MUST resolve friendly names to IDs for statuses, assignees, labels
  - AC: `--status "In Progress"` resolves to the correct workflow state ID for the team
  - AC: `--assignee "Simon"` resolves by display name (case-insensitive partial match)
  - AC: Unresolvable names produce clear error messages

- MUST follow existing agent-kit output conventions
  - AC: JSON to stdout, errors to stderr, exit codes 0/1/2

## Technical Design

### Overview

New `linear/` module following the Notion pattern. Direct GraphQL calls via httpx (synchronous —
no async needed). A thin GraphQL client handles query execution and error handling. Name-to-ID
resolution is done by querying the relevant entities (team states, users, labels) and matching.

### Code Structure

```
src/agent_kit/linear/
├── __init__.py
├── cli.py          # Click subcommands
├── client.py       # GraphQL client, queries, mutations
└── resolve.py      # Name → ID resolution (statuses, assignees, labels)
```

### Key Decisions

- **Synchronous httpx** — Linear's API is standard HTTP POST, no streaming or MCP. No need
  for async. Use `httpx.Client` directly in commands.
- **No config/scope** — the API key controls access. No need for read/write gating or scope
  config. Just register the subcommand group. No changes to agent-kit's config dataclasses.
- **Name resolution** — query the team's workflow states, workspace users, and labels as
  needed. Cache within a single command invocation (e.g. resolve status once per `issues`
  call, not per-issue). No persistent cache.
- **GraphQL queries as strings** — inline in `client.py`. No schema codegen or fragments
  library. Keep it simple.
- **Server-side filtering** — translate CLI flags into Linear's GraphQL filter syntax.
  Much more efficient than post-processing.
- **Pagination** — use `first: N` parameter matching the `--limit` value. Single page fetch,
  no cursor chasing. Default limit 50 (Linear's default page size).
- **Error handling** — `LinearClient.query()` raises `ValueError` on GraphQL errors.
  HTTP 401 → exit 2 (auth). All other errors → exit 1. No custom exception classes needed.
- **Issue identifiers** — Linear's `issue(id:)` query accepts both UUIDs and shorthand
  identifiers like `PLAT-123` per their docs. Verify during implementation; if shorthand
  doesn't work, fall back to filtering by identifier string.
- **Labels** — `--label` is repeatable (Click `multiple=True`). Multiple labels are passed
  as an array of IDs to the API.

### Config Changes

No changes to agent-kit's config system. Linear has no read/write gating or scope config.

Archie's config needs updating (separate repo at `/home/simon.downes/dev/archie/`):
- `src/archie/config.py` DEFAULT_CONFIG: add `auth.linear` and `credentials` mappings
- `persona/guidance/TOOLS.md`: add `ak linear` usage guidance

## Testing Constraint

Use the existing Linear workspace accessible via the API key. Test against real data but
avoid creating/modifying production issues — use a test project or team if available.

## Milestones

### 1. GraphQL client and team/project queries

Approach:
- Create `linear/client.py` with a `LinearClient` class wrapping httpx. Constructor takes
  API key, provides a `query(query_str, variables)` method that POSTs to
  `https://api.linear.app/graphql` and returns the parsed JSON `data` dict.
  Raises on GraphQL errors or HTTP errors.
- Register `linear` subcommand group in `cli.py`
- `LINEAR_API_KEY` check follows the same pattern as Notion's `_get_token()`
- ⚠️ Linear auth header is `Authorization: <key>` not `Authorization: Bearer <key>`

Tasks:
- Create `src/agent_kit/linear/` module with `__init__.py`
- Implement `LinearClient` in `client.py` with query execution and error handling
- Implement `ak linear teams` command
- Implement `ak linear team <id-or-key>` command (includes workflow states)
- Implement `ak linear projects` command with optional `--team` filter
- Register `linear` group in main `cli.py`

Deliverable: `ak linear teams` returns workspace teams, `ak linear team PLAT` returns
team details with workflow states.

Verify: `ak linear teams` outputs JSON. `ak linear team <key>` includes workflow states.

### 2. Issue listing and detail

Approach:
- `issues` query uses Linear's server-side filtering. Build the GraphQL filter object from
  CLI flags. Status and assignee filters need name → ID resolution.
- `resolve.py` handles lookups: query team's `states` for status names, `users` for
  assignee names, `issueLabels` for label names. Match case-insensitively.
- Issue identifiers (PLAT-123) work directly in Linear's `issue(id:)` query.
- Return a consistent field set: id, identifier, title, state name, assignee name,
  priority, labels, project name, createdAt, updatedAt.

Tasks:
- Implement `resolve.py` with functions to resolve status, assignee, and label names to IDs
- Implement `ak linear issues --team <key>` with filter flags
- Implement `ak linear issue <identifier>` for single issue detail

Deliverable: `ak linear issues --team PLAT --status "In Progress"` returns filtered issues.
`ak linear issue PLAT-123` returns full issue detail.

Verify: Both commands return valid JSON with expected fields. Filtering by status name works.

### 3. Issue create and update

Approach:
- `issueCreate` mutation takes teamId, title, and optional description, stateId, assigneeId,
  priority, labelIds. Resolve names before calling.
- `issueUpdate` mutation takes issue id and input fields. Same resolution.
- Description from `--description` flag or stdin (same pattern as Notion comments).
- Priority is 1-4 (urgent, high, medium, low) — pass through directly, Linear uses the
  same numeric scale.

Tasks:
- Implement `ak linear create-issue` with all flags
- Implement `ak linear update-issue` with all flags

Deliverable: Issues can be created and updated via CLI with friendly names for status/assignee.

Verify: Create an issue, verify it appears in Linear. Update its status, verify the change.

### 4. Comments and file uploads

Approach:
- `issue.comments` query for reading, `commentCreate` mutation for writing.
- Comment body from `--message` or stdin.
- File upload is two-step: `fileUpload` mutation returns a pre-signed `uploadUrl` and
  `assetUrl`, then PUT the file content to `uploadUrl` with correct headers. Return
  `assetUrl` for the agent to embed in markdown.
- ⚠️ The `fileUpload` mutation returns response headers that MUST be included in the PUT
  request (array of `{key, value}` pairs).

Tasks:
- Implement `ak linear comments <identifier>`
- Implement `ak linear comment <identifier> --message "..."`
- Implement `ak linear upload <file-path>`

Deliverable: Comments can be read and added. Files can be uploaded and the asset URL returned.

Verify: Read comments on an issue. Add a comment. Upload a file, use the returned URL in
a comment with markdown syntax, verify it renders in Linear.

### 5. Documentation and TOOLS.md

Tasks:
- Update agent-kit README with Linear command reference
- Update CONTRIBUTING.md if any new patterns emerged
- Add `ak linear` section to Archie's TOOLS.md guidance
- Add Linear auth config to Archie's DEFAULT_CONFIG

Deliverable: Documentation covers all Linear commands with examples.

Verify: README has complete Linear section. TOOLS.md has usage guidance.
