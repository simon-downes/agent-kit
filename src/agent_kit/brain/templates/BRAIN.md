# Brain

{{USER}}'s knowledge base — structured for both human and agent retrieval.

## Structure

| Directory | Purpose |
|-----------|---------|
| `_{{AGENT}}/` | {{AGENT}}'s operational state (memory, signals, soul) |
| `_inbox/` | Ingestion staging — files = ready, subdirs = bulk processing |
| `{{USER}}/` | Personal space (profile, goals, journal, inbox) |
| `people/` | Relationships and contacts |
| `projects/` | Lightweight project context (not code docs) |
| `knowledge/` | Durable reference knowledge grouped by domain |

## Reading

```bash
ak brain search "term1" "term2"           # multi-term ranked search
ak brain search "terraform" --limit 5     # limit results
ak brain index                            # full index
ak brain index --type people              # filter by type
ak brain index --slug alice               # lookup by slug
```

Search scores: filename/title +3, tags +2, body +1. Multiple terms boost rank.

## Writing

### Before creating anything, check for duplicates:

```bash
ak brain search "<name or topic>"
```

If a match exists, update the existing file — merge new information, don't overwrite.

### Frontmatter

All brain files should have YAML frontmatter. These fields are used for indexing:

```yaml
---
name: Entity Name
summary: One-line description
tags: [relevant, tags]
---
```

### File conventions

- Use `[[wikilinks]]` for links between entries: `[[people/jane]]`, `[[projects/tillo]]`
- One file per entity (person, project, topic)
- Knowledge grouped by domain: `knowledge/<domain>/<topic>.md`

### Conflict handling

When ingesting from a source older than existing content, don't overwrite — create a
note in `{{USER}}/inbox/` flagging the discrepancy for review. Newer information
naturally supersedes older; just update the entry.

### Provenance

Source tracking is automatic during ingestion — stored in `brain.db` (gitignored).
Query with sqlite:

```bash
sqlite3 brain.db "SELECT * FROM provenance ORDER BY ingested_at DESC LIMIT 10"
sqlite3 brain.db "SELECT * FROM provenance WHERE source_file LIKE '%weekly%'"
```

### Commit

After creating or modifying files:

```bash
ak brain reindex
ak brain commit "brain: <description>" --paths <file1> --paths index.yaml
```

Use `--paths` to stage only files you wrote — prevents sweeping up another session's
uncommitted work. Always include `index.yaml` if you ran reindex.

## Reference tracking

Record access when reading brain entries. Helps identify high-value vs stale content.

```bash
ak brain ref <path>               # record an access
ak brain refs --top 10            # most referenced
ak brain refs --stale --since 90d # unreferenced
```
