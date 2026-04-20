# Agent Kit — Google Workspace Integration

## Objective

Add read-only Google Workspace access to agent-kit as `ak google`. Covers Gmail,
Calendar, and Drive via a single shared OAuth token. Designed for context gathering
and brain ingestion — fetching emails, events, and documents as files ready for
processing.

## Requirements

### Auth

- MUST use the existing OAuth flow (`ak auth login google`) — already implemented
  - AC: `client_id` and `client_secret` read from credential store
  - AC: Access token auto-refreshed when expired

- MUST provide a shared token getter with auto-refresh for all three APIs
  - AC: Expired tokens refreshed transparently before API calls
  - AC: Auth errors produce clear messages with exit code 2

### Mail

- MUST support searching emails: `ak google mail search <query>`
  - AC: Gmail query syntax passed through (from:, to:, subject:, after:, label:, etc.)
  - AC: Returns JSON list with id, date, from, to, subject, snippet
  - AC: Supports `--limit N` (default: 20)

- MUST support listing recent emails: `ak google mail recent [--hours N]`
  - AC: Defaults to last 24 hours
  - AC: Same output format as search

- MUST support listing unread emails: `ak google mail unread [--limit N]`
  - AC: Filters to unread only
  - AC: Same output format as search

- MUST support reading a single email: `ak google mail read <id>`
  - AC: Downloads as markdown file with YAML frontmatter (from, to, cc, date, subject)
  - AC: Prefers plain text part, falls back to HTML → pandoc → markdown
  - AC: Strips inline images (signature noise)
  - AC: Real attachments saved in `<name>_attachments/` alongside the markdown file
  - AC: `--stdout` outputs body text only (no attachments)
  - AC: `--to-inbox` writes to `~/.archie/brain/_raw/inbox/`
  - AC: `--format html` outputs raw HTML

### Calendar

- MUST support listing today's events: `ak google calendar today`
  - AC: Returns JSON list with id, summary, start, end, attendees, meetLink, status

- MUST support listing upcoming events: `ak google calendar upcoming [--days N]`
  - AC: Defaults to 7 days
  - AC: Same output format as today

- MUST support reading a single event: `ak google calendar event <id>`
  - AC: Returns JSON with full detail including description, organizer, attendees

### Drive

- MUST support searching files: `ak google drive search <query> [--limit N]`
  - AC: Simple text query (name contains), not raw Drive query syntax
  - AC: Returns JSON list with id, name, mimeType, modifiedTime, owners

- MUST support listing recent files: `ak google drive recent [--days N]`
  - AC: Defaults to 7 days
  - AC: Same output format as search

- MUST support listing folder contents: `ak google drive list [--folder <id>] [--limit N]`
  - AC: Without --folder, lists root
  - AC: Flat listing (not recursive)

- MUST support fetching file content: `ak google drive fetch <id>`
  - AC: Google Docs → HTML export → pandoc → markdown. Images saved in `<name>_media/`
  - AC: Google Sheets → CSV export
  - AC: Google Slides → HTML export → pandoc → markdown
  - AC: Binary files → download as-is
  - AC: Default writes to current directory, filename from doc name
  - AC: `--stdout` outputs content to stdout (no images/attachments)
  - AC: `--to-inbox` writes to `~/.archie/brain/_raw/inbox/`
  - AC: `--format FORMAT` overrides (html, pdf, csv, text)
  - AC: `--output DIR` writes to specified directory

### General

- MUST follow agent-kit output conventions (JSON to stdout for list commands, files for
  read/fetch commands, errors to stderr, exit codes 0/1/2)

- MUST resolve `--to-inbox` path from brain config (`brain.dir` + `/_raw/inbox/`)

### Config Gating

- SHOULD support per-service enable/disable in config
  - AC: `google.mail.enabled`, `google.calendar.enabled`, `google.drive.enabled`
  - AC: Disabled services produce clear error message

## Technical Design

### Code Structure

```
src/agent_kit/google/
├── __init__.py
├── cli.py          # Click group with mail/calendar/drive subgroups
├── auth.py         # Token getter with auto-refresh
├── mail.py         # Gmail API client
├── calendar.py     # Calendar API client
└── drive.py        # Drive API client + pandoc conversion
```

### Key Decisions

- **Synchronous httpx** — same as Jira/Linear. All three Google APIs are standard REST.

- **Shared auth module** — `auth.py` provides `get_token()` that reads from credential
  store, checks expiry, auto-refreshes if needed, and returns a valid access token.
  All three clients use this.

- **Token auto-refresh** — check `expires_at` in credentials. If expired or within 60s
  of expiry, call `refresh_token()` from `oauth.py` with `client_secret`, store new
  tokens, return fresh access token. Transparent to callers.

- **File output as default for read/fetch** — unlike other agent-kit modules that output
  JSON to stdout, `mail read` and `drive fetch` write files by default. This matches
  the primary use case (download for ingestion). `--stdout` flag for pipe use cases.
  List/search commands still output JSON to stdout.

- **pandoc for HTML → markdown** — Google Docs/Slides exported as HTML, converted via
  `pandoc -f html -t markdown --wrap=none`. Images extracted with `--extract-media=DIR`
  when writing to file. pandoc must be available in PATH (added to sandbox Dockerfile).

- **Inline image stripping for email** — before passing HTML email to pandoc, strip
  `<img>` tags to remove signature logos and tracking pixels. Real attachments are
  separate MIME parts downloaded independently.

- **Gmail query passthrough** — Gmail's search syntax is powerful and well-known. Pass
  the query string directly to the API rather than building our own filter flags.

- **`--to-inbox` resolution** — reads `brain.dir` from agent-kit config, appends
  `/_raw/inbox/`. Creates the directory if it doesn't exist.

- **Config gating** — check `google.<service>.enabled` in config before any API call.
  Default: all enabled. Same pattern as Notion's read/write gating.

- **Error handling** — Google API errors return JSON with `error.message` and
  `error.code`. Parse these into `ValueError` messages. HTTP 401 → auto-refresh
  attempt, then exit 2 if still failing. HTTP 403 → exit 2 (scope issue).

### Config Changes

Agent-kit `DEFAULT_CONFIG` — add service gating under a separate top-level `google` key
(not inside `auth.google`), following the Notion pattern:

```python
"google": {
    "mail": {"enabled": True},
    "calendar": {"enabled": True},
    "drive": {"enabled": True},
},
```

The auth config (`auth.google`) remains separate and handles OAuth endpoints/scopes.

### Sandbox Changes

pandoc is added to the Archie sandbox Dockerfile at `archie/sandbox/Dockerfile` (in the
archie repo, not agent-kit). For environments without pandoc, HTML → markdown conversion
falls back to basic HTML tag stripping (headings, paragraphs, lists extracted via regex).
The fallback produces lower quality output but doesn't break the pipeline.

### Cross-Repo Changes

Agent-kit and archie are separate git repos. Agent-kit changes are the primary deliverable.
Archie changes (TOOLS.md, config, docs, Dockerfile) are committed separately in the archie
repo.

Archie changes:
- `src/archie/config.py` DEFAULT_CONFIG: add credential mappings for google
- `persona/guidance/TOOLS.md`: add `ak google` usage guidance
- `docs/getting-started.md`: add Google Workspace setup reference

## Milestones

### 1. Auth module and Calendar

Approach:
- `auth.py` provides `get_token()` — reads access_token from credential store, checks
  `expires_at`, auto-refreshes via `oauth.refresh_token()` if expired. Returns valid
  token string. All API clients call this instead of reading credentials directly.
- Calendar is the simplest API — good for validating the auth module works.
- Google Calendar API v3: `GET /calendars/primary/events` with `timeMin`/`timeMax`,
  `singleEvents=true`, `orderBy=startTime`.
- Register `google` subcommand group in main `cli.py`.
- ⚠️ Google returns times in RFC 3339 format. `singleEvents=true` is needed to expand
  recurring events.

Tasks:
- Create `src/agent_kit/google/` module with `__init__.py`
- Implement `auth.py` with `get_token()` and auto-refresh
- Add Google service gating to `DEFAULT_CONFIG` in `config.py` (mail, calendar, drive)
- Implement config gating helper in `auth.py` — check `google.<service>.enabled`
- Implement `calendar.py` — `get_events()`, `get_event()`
- Implement `cli.py` — `google` group with `calendar` subgroup: `today`, `upcoming`, `event`
- Register `google` group in main `cli.py`

Deliverable: `ak google calendar today` returns today's events with auto-refreshing auth.

Verify: `ak google calendar today` outputs JSON. `ak google calendar upcoming --days 3`
returns events for next 3 days.

### 2. Gmail search and read

Approach:
- Gmail API v1: `GET /users/me/messages` with `q` parameter for search. Returns message
  IDs, then `GET /users/me/messages/{id}` with `format=full` for content.
- Message parsing: extract headers (From, To, Cc, Date, Subject) from `payload.headers`.
  Find `text/plain` part in MIME tree, fall back to `text/html`. For HTML, strip `<img>`
  tags then pipe through `pandoc -f html -t markdown --wrap=none`.
- Attachments: iterate `payload.parts`, find parts with `filename` set, download via
  `GET /users/me/messages/{id}/attachments/{attachmentId}`. Save to `_attachments/` dir.
- File output: write markdown with YAML frontmatter. `--stdout` skips file write and
  attachments.
- `--to-inbox`: resolve from `brain.dir` config + `/_raw/inbox/`. Create dir if missing.
  If `brain.dir` not configured, raise a clear error.
- ⚠️ pandoc may not be installed in all environments. Implement a `html_to_markdown()`
  helper that tries pandoc first, falls back to basic tag stripping (extract text from
  `<p>`, `<h1>`-`<h6>`, `<li>`, `<a>` tags via regex). Log a warning when falling back.
- ⚠️ Gmail message bodies are base64url-encoded. Decode with `urlsafe_b64decode`.
- ⚠️ MIME structure can be deeply nested (multipart/mixed → multipart/alternative →
  text/plain). Walk the tree recursively to find the right part.

Tasks:
- Implement `mail.py` — `search_messages()`, `get_message()`, `list_recent()`,
  `list_unread()`, MIME parsing, attachment download
- Implement HTML → markdown conversion helper (strip images, call pandoc)
- Add `mail` subgroup to CLI: `search`, `recent`, `unread`, `read`
- Implement `--stdout`, `--to-inbox`, `--format` flags

Deliverable: `ak google mail search "from:jane"` returns matching emails.
`ak google mail read <id>` downloads email as markdown with attachments.

Verify: Search returns JSON list. Read produces a markdown file with frontmatter.
HTML-only email converts to markdown via pandoc.

### 3. Drive search, list, and fetch

Approach:
- Drive API v3: `GET /files` with `q` parameter for search, `GET /files/{id}` for
  metadata, `GET /files/{id}/export` for Google Workspace files, `GET /files/{id}?alt=media`
  for binary files.
- Google Docs/Slides: export as HTML (`mimeType=text/html`), pipe through pandoc with
  `--extract-media=DIR` for images. Filename derived from doc name (slugified).
- Google Sheets: export as CSV (`mimeType=text/csv`).
- Binary files: download directly via `alt=media`.
- Search query: wrap user's text query in `name contains '<query>' or fullText contains '<query>'`.
- ⚠️ Google Workspace files (Docs/Sheets/Slides) use export, not download. Binary files
  use download. Check `mimeType` to determine which path.
- ⚠️ pandoc `--extract-media` needs a directory path. Create `<name>_media/` alongside
  the output file.

Tasks:
- Implement `drive.py` — `search_files()`, `list_files()`, `get_recent()`, `fetch_file()`
  with export/download logic and pandoc conversion
- Add `drive` subgroup to CLI: `search`, `recent`, `list`, `fetch`
- Implement `--stdout`, `--to-inbox`, `--format`, `--output` flags
- Implement pandoc subprocess call with `--extract-media`

Deliverable: `ak google drive search "roadmap"` returns matching files.
`ak google drive fetch <id>` downloads a Google Doc as markdown with images.

Verify: Search returns JSON list. Fetch produces markdown file from a Google Doc.
CSV from a Sheet. Binary download works for a PDF.

### 4. Documentation and Archie integration

Approach:
- Follow the pattern of existing docs (linear.md, jira.md). Full command reference
  with examples.
- Archie-side changes are in a separate repo (`/home/simon.downes/dev/archie/`).
  Commit separately.
- Add pandoc to Archie's `sandbox/Dockerfile`.
- Bump agent-kit version in both `pyproject.toml` and `src/agent_kit/__init__.py`.

Tasks:
- Create `docs/google.md` with full command reference
- Update agent-kit `README.md` with Google section
- Update agent-kit `CONTRIBUTING.md` with Google module listing
- Bump agent-kit to 0.8.0 in `pyproject.toml` and `src/agent_kit/__init__.py`
- Add `ak google` section to Archie's `persona/guidance/TOOLS.md` (archie repo)
- Add Google credential mappings to Archie's `src/archie/config.py` (archie repo)
- Update Archie's `docs/getting-started.md` with Google setup reference (archie repo)
- Add `pandoc` to Archie's `sandbox/Dockerfile` (archie repo)

Deliverable: All docs updated. pandoc in sandbox. Versions bumped.

Verify: `ak google --help` shows all subcommands. Docs have complete command reference.
