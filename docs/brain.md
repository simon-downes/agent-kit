# Brain

A file-based knowledge base managed as a single git repository. Provides ranked search,
indexing, reference tracking, and git operations.

## Concepts

**Brain directory** — the root directory (default `~/.archie/brain/`) containing all
knowledge, agent state, and ingestion staging.

**Index** — `index.yaml` at the brain root providing a compact lookup of entities with
name, summary, tags, and path.

**Indexable directories** — `people/`, `projects/`, `knowledge/`. Content in these
directories is indexed by `ak brain reindex`.

**Ingestion** — `_raw/` at the brain root. Files placed here await processing into
brain entities via the `action-brain-ingest` skill.

**Attention queue** — `_inbox/` at the brain root. Items needing user review
(conflicts, decisions, flagged discrepancies).

## Setup

```bash
ak init
```

Prompts for user name and agent name. Creates the brain directory structure with a
templated `BRAIN.md` convention guide, user profile skeleton, and agent operational
files. Persists user/agent names in `~/.agent-kit/config.yaml`.

## Commands

### `ak brain search <term> [<term>...] [--limit N]`

Search across index metadata and file content. Multiple terms act as OR with scoring:
- Filename/title match: +3
- Tag match: +2
- Body content match: +1

Results ranked by match count then score.

### `ak brain index [--type <type>] [--slug <slug>]`

Query the brain index. Filter by entity type or lookup by slug.

### `ak brain reindex`

Rebuild `index.yaml` from filesystem contents. Scans `people/`, `projects/`,
`knowledge/` for markdown and YAML files.

### `ak brain commit <message> [--paths <file> ...]`

Stage and commit changes. Use `--paths` to stage specific files (concurrent safety).

### `ak brain ref <path>`

Record a brain entry access for reference tracking. Stored in SQLite (`brain.db`).

### `ak brain refs [--top N] [--stale --since Nd]`

Query reference tracking data:
- `--top N` — most referenced entries
- `--stale --since 90d` — entries not referenced in N days

### `ak brain status`

Brain directory info and git status.

### `ak brain project [name]`

Get project info from the brain. Looks for `projects/<name>/README.md` or
`projects/<name>.md`. Infers project name from cwd if not given.
