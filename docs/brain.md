# Brain

Query and manage the Archie second brain — a file-based knowledge store composed of
context directories, each an independent git repository.

## Configuration

```yaml
brain_dir: ~/.archie/brain    # default
```

The brain directory contains one or more context directories (`shared/`, `work-acme/`,
`personal/`, etc.). Each context has a standard set of entity directories and an
`index.yaml` for structured lookups.

See the [Archie brain documentation](../../docs/brain.md) for the full structure and
conventions.

## Commands

### `ak brain index [context]`

Query the brain index. Without a context, lists all available contexts.

```bash
# List contexts
ak brain index

# Show full index for a context
ak brain index shared

# Filter by entity type
ak brain index work-acme --type projects

# Lookup a specific entity
ak brain index work-acme --slug acme-api
```

| Option | Description |
|--------|-------------|
| `--type TYPE` | Filter by entity type (contacts, projects, knowledge, etc.) |
| `--slug SLUG` | Lookup a specific entity by slug |

### `ak brain create-context <name>`

Create a new brain context with the standard directory structure and initialise a git
repository.

```bash
ak brain create-context work-acme
ak brain create-context personal
```

Creates: `me/`, `contacts/`, `projects/`, `knowledge/`, `goals/`, `inbox/`, `outbox/`,
`journal/`, `raw/`, `archive/`, `.gitignore` (ignores `raw/` and `brain.db`).

### `ak brain status [context]`

Show brain status — git changes and unprocessed items in `raw/`. Without a context,
shows status for all contexts.

```bash
# All contexts
ak brain status

# Specific context
ak brain status work-acme
```

Output includes:
- `context` — context name
- `changes` — list of uncommitted changes (git porcelain format)
- `raw` — list of unprocessed files in `raw/`

### `ak brain validate [context]`

Validate brain structure and index integrity. Without a context, validates all contexts.

```bash
ak brain validate
ak brain validate shared
```

Checks:
- Standard entity directories exist
- `index.yaml` is valid YAML
- Index entries have required fields (`name`, `path`)
- Index paths point to existing files/directories
- Entities on disk are represented in the index

Exits with code 1 if any errors are found. Findings are JSON with `level` (error,
warning, info), `message`, and `context`.
