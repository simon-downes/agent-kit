# Brain

A file-based second brain managed as a directory of contexts, each an independent git
repository. Agent-kit provides the CLI tooling to create, query, and validate the
brain structure.

## Concepts

**Brain directory** — the root directory containing all contexts and the raw pipeline.
Configurable, defaults to `~/.archie/brain`.

**Contexts** — top-level subdirectories, each a separate git repo. Represent different
areas of life or work (e.g. `shared`, `work-acme`, `personal`). Separate repos allow
selective cloning per device.

**Entity directories** — standard subdirectories within each context:

| Directory   | Purpose                                    |
|-------------|--------------------------------------------|
| `me/`       | Identity, personality, preferences         |
| `contacts/` | People and relationships                   |
| `projects/` | Active work                                |
| `knowledge/`| Concepts, topics, reference material       |
| `goals/`    | Priorities, OKRs, roadmap items            |
| `inbox/`    | Actionable items awaiting review           |
| `outbox/`   | Draft messages awaiting send               |
| `journal/`  | Daily/weekly logs                          |
| `archive/`  | Retired entities                           |

These are conventions, not enforced — users structure content however they like within
them.

**Index** — each context can have an `index.yaml` providing a compact lookup of entities
(keyed by slug, with name, summary, and path). Used by LLM agents to understand what's
in the brain without reading every file.

**Raw pipeline** — `_raw/` at the brain root (outside any context) with three stages:
`inbox/` (to be processed), `processing/` (in progress), `completed/` (done, reviewable).

## Configuration

```yaml
brain:
  dir: ~/.archie/brain
  contexts:
    shared: null                                    # local-only
    work-acme: git@github.com:you/brain-acme.git    # cloned from remote
    personal: git@github.com:you/brain-personal.git
```

## Project Config

Projects live in `<context>/projects/<name>/README.md` with YAML frontmatter for
structured config and markdown body for context:

```markdown
---
name: My App
summary: Core API service
issues:
  provider: linear
  team: PLAT
slack: true
---

# My App

Core API service...
```

`ak brain project` and `ak project --config` resolve project config by matching the
current working directory name against project directories across all contexts.

## Commands

### `ak brain init [context]`

Initialise the brain or a specific context. Without arguments: creates `_raw/` pipeline
dirs and initialises/clones all configured contexts (plus `shared` if not configured).
With a context name: initialises just that one.

```bash
ak brain init                 # full setup
ak brain init work-acme       # single context
```

### `ak brain index [context]`

Query the brain index. Without a context, lists available contexts.

```bash
ak brain index                          # list contexts
ak brain index shared                   # full index
ak brain index shared --type projects   # filter by type
ak brain index shared --slug my-app     # lookup by slug
```

### `ak brain project [name]`

Get project config. Without a name, infers from current working directory.

```bash
ak brain project my-app
ak brain project              # infer from cwd
```

### `ak brain status [context]`

Show brain status — raw pipeline state and git changes per context.

```bash
ak brain status               # all contexts + raw
ak brain status shared        # single context
```

### `ak brain validate [context]`

Validate structure and index integrity. Checks entity directories, index consistency,
and git origins against config.

```bash
ak brain validate
```
