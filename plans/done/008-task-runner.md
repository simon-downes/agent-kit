# Agent Kit — Task Runner

## Objective

Add a generic task runner to agent-kit that manages the lifecycle of background tasks —
creation, execution, status tracking, and cleanup. Tasks are stored in a SQLite database.
A `run` command serves as the cron entry point, claiming pending tasks atomically and
executing them in parallel via a thread pool, with inactivity-based timeout detection.
The task runner has no knowledge of Docker or Archie — it runs arbitrary commands.

## Requirements

### Schema

- MUST store tasks in `~/.agent-kit/tasks.db` using SQLite with WAL mode
  - AC: Database created automatically on first use
- MUST include fields: `id` (INTEGER PK AUTOINCREMENT), `name` (TEXT), `status`,
  `command`, `args` (JSON array), `created_at`, `started_at`, `finished_at`, `exit_code`,
  `error`
  - AC: `status` is one of: `pending`, `running`, `done`, `failed`, `timeout`, `cancelled`
- MUST enforce unique active task names via partial unique index
  - AC: `CREATE UNIQUE INDEX idx_tasks_active_name ON tasks(name) WHERE status IN ('pending', 'running')`
  - AC: Creating a task with a name that's already pending or running raises an error
  - AC: Completed/failed/timeout/cancelled tasks with the same name don't block new creation

### Task Creation

- MUST support `ak tasks create --name <name> -- <command> [args...]`
  - AC: Prints the task ID to stdout on success
  - AC: Command and args stored separately (command as TEXT, args as JSON array)
  - AC: Status set to `pending`, `created_at` set to current UTC timestamp
  - AC: Exits with error if name already active (IntegrityError from partial unique index)

### Task Listing

- MUST support `ak tasks list [--status <status>] [--all] [--limit N]`
  - AC: Default shows only `pending` and `running` tasks ordered by `created_at` ascending
  - AC: `--all` shows tasks in all statuses
  - AC: `--status` filters by a specific status value (across all tasks, not just active)
  - AC: If both `--status` and `--all` provided, `--status` takes precedence
  - AC: Default limit 20
  - AC: Output is JSON array

### Task Status

- MUST support `ak tasks status <name-or-id>`
  - AC: Looks up by name first (exact match), then by ID prefix
  - AC: Returns JSON object with all task fields
  - AC: Includes log file path if log exists

### Task Log

- MUST support `ak tasks log <name-or-id> [--error]`
  - AC: Default outputs the stdout log file contents
  - AC: `--error` outputs the stderr (error) log file contents
  - AC: Errors if the requested log file doesn't exist

### Task Cancellation

- MUST support `ak tasks cancel <name-or-id>`
  - AC: If task is `pending`, sets status to `cancelled` and sets `finished_at`
  - AC: If task is `running`, kills the process (best-effort) and sets status to `cancelled`
  - AC: If task is in a terminal status, errors with "task already completed"
  - AC: Outputs confirmation message

### Task Execution (run)

- MUST support `ak tasks run` as the cron entry point
  - AC: Claims all `pending` tasks atomically
    (`UPDATE ... SET status = 'running' WHERE status = 'pending' RETURNING *`)
  - AC: Executes claimed tasks in parallel using `ThreadPoolExecutor` (max 4 workers)
  - AC: Each task runs via `subprocess.Popen` with stdout and stderr captured to separate
    log files in `~/.agent-kit/tasks/logs/`:
    - stdout: `<name>-<id>.log`
    - stderr: `<name>-<id>.error.log`
  - AC: On process exit, updates task with `exit_code`, `finished_at`, and `status`
    (`done` if exit code 0, `failed` otherwise)
  - AC: `error` field populated with short infrastructure message: "exit code N" for
    failures, "no log activity for Ns" for timeouts, "process disappeared" for orphans
  - AC: Process exits after all claimed tasks complete

### Timeout Detection

- MUST detect stuck tasks via log file inactivity
  - AC: While a task is running, monitor the stdout log file's mtime
  - AC: If no log activity for the configured timeout period (default 10 minutes),
    send SIGTERM, wait 10 seconds, then SIGKILL if still alive. Mark task as `timeout`.
  - AC: On each `run` invocation, check all pre-existing `running` tasks — if log files
    haven't been modified within the timeout period, mark as `timeout`
  - AC: Known limitation: tasks that produce no stdout output will be killed after the
    timeout period. All current use cases (kiro-cli headless) produce continuous output.

### Cleanup

- MUST support `ak tasks clean [--before <duration>]`
  - AC: Removes tasks with terminal status (`done`, `failed`, `timeout`, `cancelled`)
    where `finished_at` is older than the specified duration
  - AC: Also removes associated log files
  - AC: Default duration 7 days
  - AC: Duration format: `<N><unit>` where unit is `m` (minutes), `h` (hours), `d` (days)
  - AC: Outputs count of removed tasks

### Configuration

- SHOULD read timeout from config: `tasks.inactivity_timeout` (seconds, default 600)
  - AC: Added to `DEFAULT_CONFIG` in config.py

## Technical Design

### Database

- SQLite with WAL mode, created lazily on first access via `db.py`
- Auto-incrementing integer IDs — simple, sufficient for a single local database
- Active name uniqueness via partial unique index — no application-level TOCTOU race

### Module Structure

```
src/agent_kit/tasks/
├── __init__.py
├── cli.py          # Click commands: create, list, status, log, cancel, run, clean
├── client.py       # TaskClient class — DB operations, task execution
└── db.py           # Private — connection management, schema
```

### TaskClient

Constructor: `TaskClient(db_path: Path | None = None)` — defaults to
`~/.agent-kit/tasks.db`. Follows existing client pattern (BrainClient takes brain_dir).

### Execution Model

`TaskClient.run()`:
1. Check existing `running` tasks for inactivity timeout (orphan detection)
2. Claim pending tasks: `UPDATE ... SET status = 'running' WHERE status = 'pending' RETURNING *`
3. Submit each to `ThreadPoolExecutor(max_workers=4)`
4. Each thread: `Popen(cmd + args, stdout=log, stderr=err_log)`, poll loop (5s sleep)
   checking `proc.poll()` and log mtime for inactivity
5. On timeout: `proc.terminate()`, 10s grace, `proc.kill()` if needed
6. `executor.shutdown(wait=True)`, then exit

### Log Files

Directory: `~/.agent-kit/tasks/logs/`, created on first task execution.
Files: `<name>-<id>.log` (stdout) and `<name>-<id>.error.log` (stderr).

### Error Handling

Existing pattern — client raises exceptions, `@handle_errors` on CLI commands.
`ValueError` for not-found and duplicate names. `IntegrityError` caught and re-raised
as `ValueError` with a user-friendly message.

### Dependencies

No new dependencies. SQLite and `concurrent.futures` are stdlib.

## Milestones

1. **Database layer and task creation**
   Approach:
   - New `src/agent_kit/tasks/` package with `db.py`, `client.py`, `cli.py`, `__init__.py`
   - `db.py`: `get_connection(db_path)` returns a `sqlite3.Connection` with WAL mode and
     `row_factory = sqlite3.Row`. Creates schema on first call. Schema is a module-level
     `_SCHEMA` string.
   - `client.py`: `TaskClient(db_path: Path | None = None)`. Public method:
     `create(name: str, command: str, args: list[str]) -> dict`.
   - `cli.py`: `tasks` Click group. `create` command with `--name` required option and
     remaining args captured via `click.argument('args', nargs=-1)`. The first arg is the
     command, rest are args.
   - Register `tasks` group in `src/agent_kit/cli.py`
   - Tests in `tests/tasks/test_client.py` and `tests/tasks/test_cli.py` — creation,
     duplicate name rejection
   - ⚠️ The partial unique index means `IntegrityError` on duplicate active names — catch
     in client and raise `ValueError` with clear message
   Deliverable: `ak tasks create --name test-task -- echo hello` creates a pending task
   and prints its ID.
   Verify: `uv run pytest tests/tasks/ -v`

2. **Listing, status, log, and cancel commands**
   Approach:
   - `TaskClient` methods: `list_tasks(*, status, show_all, limit)`, `get(name_or_id)`,
     `get_log_path(name_or_id, error=False)`, `cancel(name_or_id)`
   - `get()` resolves by name first (exact match), then by ID prefix. Raises `ValueError`
     if not found or ambiguous prefix.
   - Log path derived from task name + id, not stored in DB
   - `cancel()`: if pending, update to cancelled + set finished_at. If running, best-effort
     note in error field (actual process kill only possible from `run`). If terminal, raise
     ValueError.
   - CLI commands: `list`, `status`, `log` (with `--error` flag), `cancel` — all with
     `@handle_errors`
   - ⚠️ `cancel` of a running task from outside the `run` process can only update the DB
     status. The `run` process poll loop should check for status changes and kill the
     process if status was changed to `cancelled` externally.
   Deliverable: `ak tasks list`, `ak tasks status <name>`, `ak tasks log <name>`, and
   `ak tasks cancel <name>` all work correctly.
   Verify: `uv run pytest tests/tasks/ -v`

3. **Task execution with timeout detection**
   Approach:
   - `TaskClient.run()` implements the full execution loop
   - Orphan detection first: query `running` tasks, check log mtimes against timeout,
     mark stale ones as `timeout`
   - Claim: `UPDATE tasks SET status='running', started_at=? WHERE status='pending' RETURNING *`
   - Thread function: open log files (create log dir if needed), `Popen([command] + args)`,
     poll loop with 5s sleep. Each iteration: check `proc.poll()`, check log mtime for
     inactivity, check DB status for external cancellation.
   - On timeout: `proc.terminate()`, `proc.wait(timeout=10)`, `proc.kill()` if needed
   - On completion: update status based on exit code
   - On external cancel detected: `proc.terminate()`, wait, update finished_at
   - `ThreadPoolExecutor(max_workers=4)`, `executor.shutdown(wait=True)`
   - Read `tasks.inactivity_timeout` from config via `load_config()`
   - Tests: mock `subprocess.Popen` to simulate completion, timeout, and cancellation.
     Use `tmp_path` for DB and log files.
   Deliverable: `ak tasks run` claims pending tasks, executes in parallel, updates status
   on completion, detects inactivity timeouts, and respects external cancellation.
   Verify: `uv run pytest tests/tasks/ -v`

4. **Cleanup, config, and documentation**
   Approach:
   - `TaskClient.clean(before: timedelta) -> int` — delete tasks with terminal status
     where `finished_at < now - before`, remove log files, return count
   - `_parse_duration(s: str) -> timedelta` — regex `^(\d+)([mhd])$`, m=minutes, h=hours,
     d=days. Raises `ValueError` on bad input. Lives in `client.py`.
   - Add `"tasks": {"inactivity_timeout": 600}` to `DEFAULT_CONFIG` in `config.py`
   - CLI: `clean` command with `--before` option (default `"7d"`)
   - Create `docs/tasks.md` with full command reference and cron setup example
   - Update `README.md` tools section
   Deliverable: `ak tasks clean` removes old tasks and logs; config timeout is respected;
   docs are complete.
   Verify: `uv run pytest tests/tasks/ -v && uv run ruff check src/ && uv run ruff format --check src/`
