# Brain

Query and manage the Archie second brain — a file-based knowledge store composed of
context directories, each an independent git repository.

## Configuration

```yaml
brain:
  dir: ~/.archie/brain          # default
  contexts:
    shared: null                # local-only (no remote repo)
    work-acme: git@github.com:you/brain-work-acme.git
    personal: git@github.com:you/brain-personal.git
```

Contexts with a repo URL are cloned on `ak brain init`. Contexts without a URL are
created locally with `git init`.

## Commands

### `ak brain init [context]`

Initialise the brain or a specific context.

Without arguments: creates the `_raw` pipeline directories and initialises/clones all
configured contexts (plus `shared` if not configured).

With a context name: initialises just that context — clones from config if a repo is
specified, otherwise creates locally.

```bash
# Full brain init (first time setup or new device)
ak brain init

# Add a single new context
ak brain init work-acme
```

Created contexts get the standard entity directories: `me/`, `contacts/`, `projects/`,
`knowledge/`, `goals/`, `inbox/`, `outbox/`, `journal/`, `archive/`.

### `ak brain index [context]`

Query the brain index. Without a context, lists all available contexts.

```bash
ak brain index
ak brain index shared
ak brain index work-acme --type projects
ak brain index work-acme --slug acme-api
```

| Option | Description |
|--------|-------------|
| `--type TYPE` | Filter by entity type |
| `--slug SLUG` | Lookup a specific entity by slug |

### `ak brain project [name]`

Get project config from the brain. Searches across all contexts for a matching
project directory. Without a name, infers from the current working directory.

```bash
ak brain project archie
ak brain project              # infers from cwd
```

Output includes the project's frontmatter plus `context` and `path`.

### `ak brain status [context]`

Show brain status. Without a context, shows overall status including the `_raw`
pipeline and all contexts.

```bash
ak brain status
ak brain status shared
```

Overall status includes:
- `raw.inbox` — items waiting to be processed
- `raw.processing` — items currently being processed
- `raw.completed` — processed items (can be cleaned up)
- `contexts` — git status per context

### `ak brain validate [context]`

Validate brain structure and index integrity. Without a context, validates all
contexts and checks git origins against config.

```bash
ak brain validate
ak brain validate shared
```

Checks:
- Standard entity directories exist
- `index.yaml` is valid YAML with correct structure
- Index entries have required fields and point to existing paths
- Entities on disk are represented in the index
- Git remote origins match configured repos

Exits with code 1 if any errors are found.

## Raw Pipeline

The `_raw` directory sits at the brain root (not inside any context) and provides a
simple processing pipeline:

```
~/.archie/brain/
├── _raw/
│   ├── inbox/          # drop content here for processing
│   ├── processing/     # items being worked on
│   └── completed/      # done, available for review
├── shared/
├── work-acme/
└── ...
```

Content is dropped into `inbox/`. The ingestion process moves items to `processing/`
while working, then to `completed/` when done. The LLM determines which context(s)
to update based on the content.
