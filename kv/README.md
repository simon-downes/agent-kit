# kv

A simple, fast key-value store for the command line.

## Purpose

`kv` provides persistent key-value storage with optional expiry, backed by SQLite. Use it for temporary state, configuration values, or any data you need to persist between command invocations.

## Features

- Simple key-value storage with string values
- Optional TTL (time-to-live) for automatic expiry
- Stdin support for piping values
- Pretty output with rich formatting
- Plain output mode for scripting
- Automatic cleanup of expired entries
- Secure file permissions (600)

## Installation

```bash
# Install globally
uv tool install git+https://github.com/simon-downes/cli-tools.git --subdirectory kv

# Or run directly without installing
uvx --from git+https://github.com/simon-downes/cli-tools.git --subdirectory kv kv --help
```

## Usage

### Basic Operations

```bash
# Set a value
kv set my-key "my value"

# Get a value
kv get my-key
# Output: my value

# List all keys
kv list
# ┏━━━━━━━━┳━━━━━━━━━┓
# ┃ Key    ┃ Expires ┃
# ┡━━━━━━━━╇━━━━━━━━━┩
# │ my-key │ never   │
# └────────┴─────────┘

# Remove a key
kv rm my-key
```

### Stdin Input

```bash
# Pipe value from stdin
echo "value from pipe" | kv set my-key

# Redirect from file
kv set config < config.json

# Multi-line values
cat <<EOF | kv set multi-line
line 1
line 2
line 3
EOF
```

### Expiry

```bash
# Set a value
kv set temp-key "temporary value"

# Set expiry (TTL in seconds)
kv expire temp-key 3600  # Expires in 1 hour

# List shows expiry time
kv list
# ┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
# ┃ Key      ┃ Expires             ┃
# ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
# │ temp-key │ 2026-03-03 23:50:00 │
# └──────────┴─────────────────────┘

# After expiry, get returns exit code 3
kv get temp-key
# Exit code: 3

# Clean up expired entries
kv clean
# Removed 1 expired entries
```

### Plain Output for Scripting

```bash
# Plain list output (tab-separated)
kv list --plain
# my-key	never
# temp-key	2026-03-03 23:50:00

# Use with awk, cut, etc.
kv list --plain | cut -f1 | while read key; do
  echo "Processing $key"
done
```

## Exit Codes

`kv` uses specific exit codes for different scenarios:

| Exit Code | Meaning | Commands |
|-----------|---------|----------|
| 0 | Success | All commands |
| 1 | Invalid input (e.g., bad key format) | `set` |
| 2 | Key not found | `get`, `rm`, `expire` |
| 3 | Key expired | `get` |

### Examples

```bash
# Check if key exists
if kv get my-key >/dev/null 2>&1; then
  echo "Key exists and is not expired"
fi

# Handle different error cases
kv get my-key
case $? in
  0) echo "Success" ;;
  2) echo "Key not found" ;;
  3) echo "Key expired" ;;
esac
```

## Key Requirements

Keys must follow these rules:

- **Format:** lower-kebab-case (lowercase letters, numbers, hyphens)
- **Length:** Maximum 100 characters
- **Pattern:** Must match `^[a-z0-9]+(-[a-z0-9]+)*$`

### Valid Keys

```bash
kv set my-key "value"           # ✓
kv set a "value"                # ✓
kv set key-with-numbers-123 "value"  # ✓
```

### Invalid Keys

```bash
kv set UPPERCASE "value"        # ✗ No uppercase
kv set has_underscore "value"   # ✗ No underscores
kv set "has space" "value"      # ✗ No spaces
kv set -starts-dash "value"     # ✗ Can't start with hyphen
kv set ends-dash- "value"       # ✗ Can't end with hyphen
```

## Database Location

By default, `kv` stores data in `~/.cli-tools/kv/db`. You can override this with the `KV_DB` environment variable:

```bash
# Use custom database location
export KV_DB=/tmp/my-kv.db
kv set test "value"

# Or per-command
KV_DB=/tmp/other.db kv list
```

The database file is created with permissions `600` (owner read/write only) for security.

## Commands Reference

### `kv set <key> [value]`

Set a key-value pair. If value is omitted, reads from stdin.

**Options:** None

**Exit codes:** 0 (success), 1 (invalid key)

### `kv get <key>`

Get the value for a key. Prints value to stdout.

**Options:** None

**Exit codes:** 0 (success), 2 (not found), 3 (expired)

### `kv list [--plain]`

List all keys with their expiry times.

**Options:**
- `--plain` - Output in tab-separated format for scripting

**Exit codes:** 0 (success)

### `kv expire <key> <ttl>`

Set expiry for a key. TTL is in seconds.

**Options:** None

**Exit codes:** 0 (success), 2 (key not found)

### `kv rm <key>`

Remove a key.

**Options:** None

**Exit codes:** 0 (success), 2 (key not found)

### `kv clean`

Remove all expired entries.

**Options:** None

**Exit codes:** 0 (success)

## Technical Details

### Architecture

- **CLI Framework:** click for argument parsing and command structure
- **Database:** SQLite3 with single table schema
- **Output:** rich for formatted tables and colored output
- **Type Safety:** Full mypy strict mode compliance

### Database Schema

```sql
CREATE TABLE kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    expires_at DATETIME
);
```

### Dependencies

- `click>=8.1.0` - CLI framework
- `rich>=13.0.0` - Terminal formatting

### Development

```bash
# Run tests
cd kv && uv run pytest -v

# Run integration tests
./tests/integration_test.sh

# Type check
uv run mypy src/

# Lint and format
uv run ruff check .
uv run black .
```

### Project Structure

```
kv/
├── pyproject.toml
├── README.md
├── src/kv/
│   ├── __init__.py
│   ├── cli.py      # Click commands and CLI interface
│   └── db.py       # Database operations and validation
└── tests/
    ├── test_cli.py           # CLI tests
    ├── test_db.py            # Database unit tests
    └── integration_test.sh   # End-to-end tests
```
