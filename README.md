# Agent Kit

Unified CLI toolkit for development workflows: key-value storage, activity logging, OAuth authentication, Notion integration, and environment checks.

## Installation

```bash
# Install with uv
uv tool install git+https://github.com/simon-downes/agent-kit.git

# Or install from local directory
uv tool install .
```

## Configuration

All data is stored in `~/.agent-kit/`:
- `kv/db` - Key-value store database
- `log/db` - Activity log database
- `tools.yaml` - Tool check configuration
- OAuth tokens stored in kv

## Tools

### check - Environment Checks

Verify tool installation and authentication status.

```bash
# Check all configured tools
ak check

# Check specific tools
ak check gh aws

# Verbose output with auth details
ak check -v
```

Configuration: `~/.agent-kit/tools.yaml`

### kv - Key-Value Store

Simple key-value storage with optional expiry, backed by SQLite.

```bash
# Set a value
ak kv set my-key "my value"

# Get a value
ak kv get my-key

# List all keys
ak kv list

# Set with expiry (TTL in seconds)
ak kv set temp-key "expires soon"
ak kv expire temp-key 3600

# Remove a key
ak kv rm my-key

# Clean expired entries
ak kv clean
```

**Use cases:**
- Store API tokens and credentials
- Temporary configuration
- Cache data with TTL

### log - Activity Log

Capture and retrieve project activity across sessions. Auto-detects project from current directory.

```bash
# Add entry (project auto-detected)
ak log add --kind decision "chose uv over pip for dependency management"
ak log add --kind change "migrated auth module to OAuth2" --topic auth

# Add with explicit project
ak log add --kind change "fixed auth bug" --project my-app

# Add from stdin
echo "Long description..." | ak log add --kind note -

# List entries
ak log list
ak log list --kind decision --limit 5
ak log list --since 7d
ak log list --since 2026-03-01 --until 2026-03-15

# Cross-project queries (omit --project)
ak log list --kind issue

# JSON output
ak log list --json

# View statistics
ak log stats
ak log stats --project my-app
```

**Project resolution** (when `--project` not specified):
1. First subdirectory under `~/dev` if cwd is under `~/dev`
2. Git repository root name (directory containing `.git`)
3. Current directory path with `/` replaced by `-`

**Entry kinds:**
- `task` - Completed unit of work
- `decision` - Technical choices and rationale
- `change` - Modifications to files or system state
- `issue` - Problems and blockers
- `note` - General observations
- `request` - Questions answered or information provided

**Use cases:**
- Track decisions and their rationale
- Capture activity for trend analysis
- Record issues and resolutions
- Provide historical context across sessions

### oauth - OAuth Authentication

OAuth 2.0 authentication with PKCE for SaaS providers.

```bash
# Login to a provider
ak oauth login notion

# Check authentication status
ak oauth status notion

# Logout
ak oauth logout notion

# List available providers
ak oauth providers
```

**Supported providers:**
- Notion
- GitHub
- Google

Tokens are stored securely in the kv store.

### notion - Notion Integration

Search and fetch Notion pages via MCP.

```bash
# Search for pages
ak notion search "project notes"

# Fetch a specific page
ak notion fetch <page-id>

# Output formats
ak notion fetch <page-id> --format markdown
ak notion fetch <page-id> --format json
```

Requires authentication via `ak oauth login notion`.

### project - Project Detection

Show the resolved project name for a directory.

```bash
# Current directory
ak project

# Specific path
ak project /path/to/project
```

Used internally by `ak log` for auto-detection.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.
