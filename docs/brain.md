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

### `ak brain search <term> [<term>...] [--type <type>] [--limit N]`

Search across index metadata and file content. Multiple terms act as OR with scoring:
- Filename/title match: +3
- Tag match: +2
- Body content match: +1

Results ranked by match count then score. Files matching more terms rank higher.

Multi-word terms (e.g. `"hermes agent"`) try exact phrase first, fall back to individual
word matching if no exact hit. Stopwords are removed during word-level matching.

Use `--type` to filter results by entity type (e.g. `memory`, `people`, `projects`,
`knowledge`).

**Search effectively:**
- Use short keywords, not sentences: `"terraform" "vpc"` not `"what is the terraform vpc module"`
- Separate arguments for independent concepts — each is an independent OR term
- Multi-word phrases are fine for known names: `"hermes agent"`, `"batch memory"`
- When results are empty, go broader (fewer/shorter terms), not more specific

### `ak brain index [--type <type>] [--slug <slug>]`

Query the brain index. Filter by entity type or lookup by slug.

### `ak brain read <path>`

Read a brain file by its relative path (as returned by search results). Outputs the
file content to stdout.

```bash
ak brain read "_archie/memory/2026-05-29-apps-4208.md"
ak brain read "people/alice.md"
```

### `ak brain memory [--project <name>] [--limit N]`

Read recent memory files. Returns the most recent N memory files (default 2), optionally
filtered by project tag.

```bash
ak brain memory                        # last 2 memories
ak brain memory --project apps         # last 2 for project "apps"
ak brain memory --project archie --limit 5
```

Output includes file path, name, and full content for each entry.

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
