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

Search the brain:
```bash
ak brain search "term1" "term2"
```

Record a reference (helps identify high-value entries):
```bash
ak brain ref <path>
```

Query references:
```bash
ak brain refs --top 10
ak brain refs --stale --since 90d
```

Reindex after manual changes:
```bash
ak brain reindex
```
