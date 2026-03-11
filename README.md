# Agent Kit

Unified CLI toolkit for development workflows: key-value storage, OAuth authentication, Notion integration, and agent memory.

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
- `mem/db` - Agent memory database
- OAuth tokens stored in kv

## Tools

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

### mem - Agent Memory

Persistent memory storage for AI agents across sessions and projects.

```bash
# Add a memory (project auto-detected from current directory)
ak mem add --kind decision "Switched to REST API for simplicity"

# Add with explicit project
ak mem add --project my-project --kind change "Implemented rate limiting"

# Add with optional fields
ak mem add \
  --kind change \
  --topic api-design \
  --ref abc123 \
  --metadata '{"author": "agent"}' \
  "Implemented rate limiting"

# Add from stdin
echo "Long summary..." | ak mem add --kind note -

# List recent memories for current project
ak mem list

# List for specific project
ak mem list --project my-project

# Filter by kind or topic
ak mem list --kind decision
ak mem list --topic api-design

# Limit results (default: 25, max: 100)
ak mem list --limit 50

# JSON output
ak mem list --json

# View statistics
ak mem stats
```

**Project resolution** (when `--project` not specified):
1. First subdirectory under `~/dev` if cwd is under `~/dev`
2. Git repository root name (directory containing `.git`)
3. Current directory path with `/` replaced by `-`

**Memory kinds:**
- `decision` - Architectural/technical decisions
- `change` - Significant code changes
- `issue` - Problems and resolutions
- `context` - Project conventions and constraints
- `task` - Work completed or in progress
- `note` - General observations
- `pattern` - Recurring patterns in codebase
- `dependency` - External systems and integrations
- `experiment` - Things tried that didn't work

**Use cases:**
- Capture agent decisions and context
- Track project evolution over time
- Provide historical context to agents
- Document architectural patterns

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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.
