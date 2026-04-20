# Google Workspace

Read-only access to Gmail, Calendar, and Google Drive via a single shared OAuth token.

## Credentials

Requires a Google Cloud project with OAuth Desktop App credentials. See the
[setup guide](../docs/google-workspace-setup.md) for step-by-step instructions.

```bash
ak auth set google client_id
ak auth set google client_secret
ak auth login google
```

Tokens auto-refresh transparently. If refresh fails, re-run `ak auth login google`.

## Commands

### Mail

#### `ak google mail search <query>`

Search emails using Gmail query syntax. Supports `from:`, `to:`, `subject:`,
`after:`, `before:`, `label:`, `has:attachment`, etc.

```bash
ak google mail search "from:jane subject:platform"
ak google mail search "after:2026/04/01 label:important"
```

| Option | Description |
|--------|-------------|
| `--limit N` | Maximum results (default: 20) |

#### `ak google mail recent`

List recent emails.

```bash
ak google mail recent
ak google mail recent --hours 8
```

| Option | Description |
|--------|-------------|
| `--hours N` | Hours to look back (default: 24) |
| `--limit N` | Maximum results (default: 20) |

#### `ak google mail unread`

List unread emails.

```bash
ak google mail unread --limit 10
```

#### `ak google mail read <message-id>`

Download an email as markdown with YAML frontmatter and attachments.

```bash
ak google mail read 18f3a2b4c5d6e7f8
ak google mail read 18f3a2b4c5d6e7f8 --to-inbox
ak google mail read 18f3a2b4c5d6e7f8 --stdout
```

| Option | Description |
|--------|-------------|
| `--stdout` | Output body text to stdout (no file, no attachments) |
| `--to-inbox` | Write to brain raw inbox (`_raw/inbox/`) |
| `--output DIR` | Write to specified directory |

### Calendar

#### `ak google calendar today`

List today's events.

```bash
ak google calendar today
```

#### `ak google calendar upcoming`

List upcoming events.

```bash
ak google calendar upcoming
ak google calendar upcoming --days 3
```

| Option | Description |
|--------|-------------|
| `--days N` | Days ahead (default: 7) |

#### `ak google calendar event <event-id>`

Get event details including description, organizer, and attendees.

```bash
ak google calendar event abc123def456
```

### Drive

#### `ak google drive search <query>`

Search files by name or content.

```bash
ak google drive search "roadmap"
ak google drive search "quarterly review" --limit 5
```

| Option | Description |
|--------|-------------|
| `--limit N` | Maximum results (default: 20) |

#### `ak google drive recent`

List recently modified files.

```bash
ak google drive recent
ak google drive recent --days 1
```

| Option | Description |
|--------|-------------|
| `--days N` | Days to look back (default: 7) |
| `--limit N` | Maximum results (default: 20) |

#### `ak google drive list`

List folder contents.

```bash
ak google drive list
ak google drive list --folder 1abc2def3ghi
```

| Option | Description |
|--------|-------------|
| `--folder ID` | Folder ID (default: root) |
| `--limit N` | Maximum results (default: 50) |

#### `ak google drive fetch <file-id>`

Fetch a file. Google Docs/Slides export as markdown (via pandoc), Sheets as CSV,
binary files download as-is.

```bash
ak google drive fetch 1abc2def3ghi
ak google drive fetch 1abc2def3ghi --to-inbox
ak google drive fetch 1abc2def3ghi --stdout
ak google drive fetch 1abc2def3ghi --format pdf
```

| Option | Description |
|--------|-------------|
| `--stdout` | Output content to stdout |
| `--to-inbox` | Write to brain raw inbox (`_raw/inbox/`) |
| `--output DIR` | Write to specified directory |
| `--format FMT` | Export format: html, pdf, csv, text |

## Config

Per-service enable/disable:

```yaml
google:
  mail:
    enabled: true
  calendar:
    enabled: true
  drive:
    enabled: true
```
