# Agent Kit — Session Digest

## Objective

Add `ak digest` command that processes raw kiro-cli session JSONL files into a
compact, structured YAML format optimised for LLM analysis. Strips tool output
noise (file contents, command output, search results) while preserving everything
needed for downstream analysis: user messages, agent reasoning, tool metadata, and
error details.

## Background

Raw session JSONL files store everything verbatim — full file contents from reads,
complete command output from shell, documentation from introspect. A typical session
is 500KB-2.4MB, of which ~90% is tool output that has no analytical value after the
session ends.

The digested format retains:
- User messages (verbatim — ground truth for corrections and intent)
- Agent response text (reasoning, decisions — stripped of tool-use blocks)
- Tool call metadata (name, target, success/failure, error message)
- Tool use IDs (for drilling back into raw JSONL if full output is ever needed)
- Timestamps (from Prompt entries)

Output location derived from agent-kit config: `<brain.dir>/_<agent>/logs/`.

## Output Format

Filename: `YYYY-MM-DD-<project>-<session_id>.yaml`

Where `project` is the resolved project name or `general` for non-project sessions.

```yaml
session_id: 54d5af30-52c4-4051-aaa9-9ab14165382a
project: archie
started: "2026-04-29 22:13:11"
ended: "2026-05-06 23:38:06"
turns:
  - prompt_id: c027de80-83ed-4955-b171-60870fd57bb5
    when: "2026-04-29 22:13:37"
    user: "given that we now have --bg lets review the original plan..."
    assistant: |
      INTENT: DISCUSS — reviewing whether the background tasks plan is still needed...
      You're right that --bg covers the host-side use case cleanly. The remaining gap is...
    tools:
      - id: tooluse_hHZ7MdQi4gdWb1xOCNaa7R
        name: glob
        target: "persona/skills/**"
        success: true
      - id: tooluse_5bNKuNrxrca7ns4Eh23s01
        name: read
        target: "plans/004-background-tasks.md"
        success: true
      - id: tooluse_OdCw62cSY50VRpQALmYjo8
        name: shell
        target: "uv run ruff check src/"
        success: false
        error: "exit status: 2 — No module named ruff"
```

### Field Definitions

| Field | Source | Notes |
|-------|--------|-------|
| `session_id` | Session JSON metadata | |
| `project` | Resolved from `cwd` in session JSON | Same logic as `project.py` |
| `started` | `created_at` from session JSON | `YYYY-MM-DD hh:mm:ss` |
| `ended` | `updated_at` from session JSON | `YYYY-MM-DD hh:mm:ss` |
| `prompt_id` | `message_id` from Prompt entry | Enables drill-back to raw JSONL |
| `when` | `meta.timestamp` from Prompt entry | `YYYY-MM-DD hh:mm:ss` |
| `user` | Text content from Prompt entry | Verbatim |
| `assistant` | Text content from AssistantMessage entries | Tool-use blocks stripped |
| `tools[].id` | `toolUseId` from AssistantMessage toolUse | Enables drill-back |
| `tools[].name` | Tool name from toolUse entry | |
| `tools[].target` | Extracted from tool input (see below) | Short summary of what was targeted |
| `tools[].success` | `status` from corresponding ToolResults | |
| `tools[].error` | Error content (only when failed) | Truncated to 500 chars |

### Target Extraction Rules

The `target` field summarises what the tool operated on:

| Tool | Target extraction |
|------|-------------------|
| `read` | File path from operations[0].path |
| `write` | File path |
| `shell` | The command string (truncated to 200 chars) |
| `glob` | The pattern |
| `grep` | The pattern |
| `code` | Operation + symbol/path |
| `web_search` | The query |
| `web_fetch` / `fetch` | The URL |
| `use_aws` | `service_name + operation_name` |
| `subagent` | Task description (truncated to 100 chars) |
| Other | First meaningful string field from input (truncated) |

### Error Capture Rules

When `success` is false:
- Tool validation errors: full error message (e.g. "The provided old_str was not found")
- Shell non-zero exit: `"exit status: N — <first line of stderr>"` (truncated to 500 chars)
- Other: first 500 chars of error content

When `success` is true: no `error` field.

### Assistant Text Extraction

From AssistantMessage entries within a turn:
1. Iterate `content` array
2. Keep items where `kind == "text"` — extract the `data` field
3. Skip items where `kind == "toolUse"` (these are captured in `tools[]`)
4. Join text parts with newline
5. Trim to 2000 chars per turn (captures reasoning without unbounded growth)

## Design Decisions

### Freshness check

The output is deterministic — same input always produces same output. The script
uses mtime comparison to decide what to process:

- Output file doesn't exist → process
- Source JSONL mtime > output file mtime → reprocess (full regeneration, overwrite)
- Source JSONL mtime ≤ output file mtime → skip

Full regeneration is cheap (parsing 2MB JSONL and writing 20KB YAML takes milliseconds)
and avoids complexity of append/partial-update logic. Safe to run on a cron interval —
active sessions will be regenerated on each run until they stop changing.

### Session filtering

Skips sessions that aren't useful for analysis:
- No JSONL file (empty session)
- No Prompt entries (no user interaction)
- No `agent_name` in session_state (subagent sessions — these are fragments of a
  parent session, not standalone conversations)

### No credentials required

This command reads local files only (kiro-cli session directory). No API calls,
no auth needed.

### Output directory

Derived from config: `Path(config["brain"]["dir"]) / f"_{config['agent']}" / "logs"`.
Created automatically if it doesn't exist.

## CLI Interface

```
ak digest                          # process all sessions
ak digest --session <id>           # process a specific session
ak digest --since <timestamp>      # only sessions updated after (unix ms)
ak digest --output <dir>           # override output directory
```

## Requirements

### Client (`digest/client.py`)

- MUST parse kiro-cli session files into the structured format
  - AC: Reads session metadata from `<session_id>.json`
  - AC: Reads conversation data from `<session_id>.jsonl`
  - AC: Splits on Prompt entries to identify turns
  - AC: Extracts user text verbatim from Prompt content
  - AC: Extracts assistant text with toolUse blocks stripped, trimmed to 2000 chars
  - AC: Extracts tool metadata: name, target, success, error
  - AC: Resolves project from session cwd using existing `resolve_project()` logic
  - AC: Formats timestamps as `YYYY-MM-DD hh:mm:ss`

- MUST implement target extraction per tool type
  - AC: Each tool type maps to a specific input field for the target summary
  - AC: Unknown tools fall back to first meaningful string field
  - AC: Targets truncated to documented limits (200 chars shell, 100 chars subagent)

- MUST implement error extraction
  - AC: Tool validation errors captured in full
  - AC: Shell errors include exit status and first line of stderr
  - AC: All errors truncated to 500 chars
  - AC: No error field when success is true

### CLI (`digest/cli.py`)

- MUST provide `ak digest` command
  - AC: Default processes all sessions, skipping up-to-date outputs
  - AC: `--session <id>` processes a specific session (forces regeneration)
  - AC: `--since <timestamp>` filters to sessions updated after timestamp
  - AC: `--output <dir>` overrides output directory
  - AC: Prints summary to stderr (processed, skipped, errors)
  - AC: Uses `@handle_errors` decorator
  - AC: Output directory created if it doesn't exist

- MUST implement freshness check
  - AC: Skips sessions where output mtime ≥ source JSONL mtime
  - AC: Regenerates when source is newer than output
  - AC: `--session` flag bypasses freshness check (always regenerates)

### Tests (`tests/digest/`)

- MUST have unit tests for the client
  - AC: Test turn splitting (Prompt boundaries)
  - AC: Test assistant text extraction (toolUse stripped)
  - AC: Test target extraction for each tool type
  - AC: Test error extraction (validation errors, shell errors)
  - AC: Test session filtering (skip subagents, skip empty)
  - AC: Test freshness check logic
  - AC: Test project resolution from cwd
  - AC: Tests use fixture JSONL data, no real session files

### Documentation (`docs/digest.md`)

- MUST document the command and output format
  - AC: Command usage and options
  - AC: Output format specification
  - AC: Target extraction rules
  - AC: Error capture rules
  - AC: Relationship to raw session files (drill-back via toolUseId)

## Milestones

1. **Client implementation**
   Approach:
   - Create `src/agent_kit/digest/` with `__init__.py`, `client.py`
   - `DigestClient` class with:
     - `__init__(sessions_dir, output_dir)` — paths to kiro sessions and output
     - `digest_all(since=None)` — process all sessions, return summary
     - `digest_session(session_id)` — process single session, return output path
     - `_parse_session(json_path, jsonl_path)` — parse into structured dict
     - `_parse_turns(jsonl_path)` — split JSONL into turns
     - `_extract_assistant_text(content_items)` — strip toolUse, join text
     - `_extract_tool_meta(tool_use, tool_results)` — name, target, success, error
     - `_extract_target(tool_name, tool_input)` — dispatch on tool type
     - `_extract_error(tool_result)` — error message extraction
     - `_is_fresh(source_path, output_path)` — mtime comparison
   - Use `project.resolve_project()` for project resolution from cwd
   - Output as YAML via PyYAML (already a dependency)
   Deliverable: Client that converts raw sessions to structured YAML.
   Verify: Unit tests pass. Manual run against real sessions produces expected format.

2. **CLI and registration**
   Approach:
   - Create `src/agent_kit/digest/cli.py` with Click command
   - `ak digest` as a top-level command (not a group — single action)
   - Resolve output dir from config: `brain.dir / _<agent> / logs`
   - Resolve sessions dir: `~/.kiro/sessions/cli/`
   - Register in `src/agent_kit/cli.py`
   - Print summary to stderr: `Processed: N, Skipped: M, Errors: E`
   Deliverable: `ak digest` works end-to-end.
   Verify: Run against real sessions. Confirm files appear in brain logs directory.
   Run again — all skipped. Touch a session file — only that one reprocessed.

3. **Tests and documentation**
   Approach:
   - Create `tests/digest/` with `test_client.py`
   - Fixture data: minimal JSONL with Prompt, AssistantMessage (text + toolUse),
     ToolResults (success and error cases)
   - Test each extraction function independently
   - Test end-to-end digest of a fixture session
   - Create `docs/digest.md` with command reference and format spec
   - Update README.md tools section
   Deliverable: Full test coverage and documentation.
   Verify: `uv run pytest tests/digest/ -v` passes. Docs match implementation.
