# Brain

{{USER}}'s knowledge base — structured for both human and agent retrieval.

## Structure

| Directory | Purpose |
|-----------|---------|
| `_{{AGENT}}/` | {{AGENT}}'s operational state (memory, signals, soul, logs) |
| `_inbox/` | Ingestion staging — files ready for processing |
| `{{USER}}/` | Personal space (profile, goals, journal, inbox) |
| `people/` | Relationships and contacts |
| `projects/` | Lightweight project context (not code docs) |
| `knowledge/` | Durable reference knowledge grouped by domain |

## Conventions

### Where content belongs

- **Project architecture, decisions, code docs** → in the repo (docs/, ADRs)
- **Personal goals, people, life context** → brain
- **Agent operational state** → `_{{AGENT}}/`
- **Project-specific context that isn't code** → `projects/<name>/`

### Project directories

Projects can have any internal structure but commonly include:
- `context.md` — current focus, status, lightweight summary
- `journal/` — dated entries, meeting notes, weekly updates
- `decisions/` — key decisions with context and rationale

### File conventions

- Use `[[wikilinks]]` for associative links: `[[people/jane]]`, `[[projects/tillo]]`
- Frontmatter (optional): `date`, `tags`, `updated`
- One file per entity (person, project, topic)

### Ingestion

- Files directly in `_inbox/` are ready for processing
- Subdirectories in `_inbox/` are staging areas for bulk/multi-step work
- Processed files are removed from `_inbox/`

## Interaction

### Search

```bash
ak brain search "term1" "term2"
ak brain search "terraform" "module" --limit 5
```

Multiple terms act as OR with scoring. Results ranked by:
- Filename/title match: +3
- Tag match: +2
- Body content match: +1

More terms matching the same file boost its rank.

### Index

```bash
ak brain index                    # full index
ak brain index --type people      # filter by entity type
ak brain index --slug alice       # lookup specific entity
```

### Writing and committing

After creating or modifying files:

```bash
ak brain reindex
ak brain commit "brain: <description>" --paths <file1> --paths <file2> --paths index.yaml
```

Use `--paths` to stage only the files you wrote — prevents sweeping up another
session's uncommitted work. Always include `index.yaml` if you ran reindex.

### Reference tracking

```bash
ak brain ref <path>               # record an access
ak brain refs --top 10            # most referenced entries
ak brain refs --stale --since 90d # unreferenced entries
```
