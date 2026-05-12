# ak digest

Converts raw kiro-cli session JSONL files into compact structured YAML for analysis.
Strips tool output noise while preserving user messages, agent reasoning, tool metadata,
and error details.

## Usage

```bash
ak digest                          # process all sessions
ak digest --session <id>           # process a specific session (forces regeneration)
ak digest --since <timestamp>      # only sessions updated after (unix ms)
ak digest --output <dir>           # override output directory
```

## Output

Files written to `<brain_dir>/_<agent>/logs/` (derived from config).

Filename format: `YYYY-MM-DD-<project>-<session_id>.yaml`

### Structure

```yaml
session_id: abc-123
project: archie
started: "2026-05-09 14:30:00"
ended: "2026-05-09 17:10:00"
turns:
  - prompt_id: p1-uuid
    when: "2026-05-09 14:30:37"
    user: "the user's message verbatim"
    assistant: |
      Agent reasoning text (tool-use blocks stripped, max 2000 chars)
    tools:
      - id: tooluse_abc123
        name: shell
        target: "uv run pytest tests/ -v"
        success: true
      - id: tooluse_def456
        name: write
        target: "/path/to/file.py"
        success: false
        error: "The provided old_str was not found in the file"
```

### Fields

| Field | Description |
|-------|-------------|
| `session_id` | Kiro-cli session identifier |
| `project` | Resolved from session working directory |
| `started` / `ended` | Session creation and last update time |
| `prompt_id` | Message ID for drill-back to raw JSONL |
| `when` | Timestamp of the user prompt |
| `user` | User message (verbatim) |
| `assistant` | Agent text with tool blocks stripped (max 2000 chars) |
| `tools[].id` | Tool use ID for drill-back to raw JSONL |
| `tools[].name` | Tool name |
| `tools[].target` | Short summary of what was targeted |
| `tools[].success` | Whether the tool call succeeded |
| `tools[].error` | Error message (only present on failure, max 500 chars) |

### Target Extraction

| Tool | Target |
|------|--------|
| `read` | File path |
| `write` | File path |
| `shell` | Command (max 200 chars) |
| `glob` | Pattern |
| `grep` | Pattern |
| `web_search` | Query |
| `use_aws` | Service + operation |
| `subagent` | Task (max 100 chars) |

## Freshness

The script uses mtime comparison — if the source JSONL is newer than the output YAML,
the file is regenerated. Safe to run on a cron interval.

## Drill-back

To retrieve full tool output for a specific call:

```bash
jq 'select(.kind == "ToolResults") | .data.content[] | select(.data.toolUseId == "tooluse_abc123")' \
  ~/.kiro/sessions/cli/<session_id>.jsonl
```

## Filtering

Sessions are skipped if they:
- Have no JSONL file
- Have no Prompt entries
- Are subagent sessions (no `agent_name` in session state)
