# Tasks — Background Task Runner

Generic task runner for managing background command execution. Tasks are stored in a
SQLite database with lifecycle tracking, parallel execution, and inactivity-based
timeout detection.

## Setup

No additional credentials required. The task database is created automatically at
`~/.agent-kit/tasks.db` on first use.

### Cron Setup

Add to your crontab to process pending tasks every minute:

```bash
crontab -e
# Add:
* * * * * ak tasks run
```

## Commands

### Create a Task

```bash
ak tasks create --name <name> -- <command> [args...]
```

Creates a pending task. The name must be unique among active (pending/running) tasks.
Prints the task ID on success.

```bash
ak tasks create --name research-gw -- archie shell -- kiro-cli chat --no-interactive --trust-all-tools "research gateway API"
ak tasks create --name memory-update -- archie shell -- kiro-cli chat --no-interactive --trust-all-tools "run memory pipeline"
```

### List Tasks

```bash
ak tasks list [--status <status>] [--all] [--limit N]
```

Default shows pending and running tasks, oldest first. Use `--all` for all statuses,
`--status` to filter by a specific status.

Statuses: `pending`, `running`, `done`, `failed`, `timeout`, `cancelled`.

### Task Status

```bash
ak tasks status <name-or-id>
```

Show details for a task. Looks up by name first, then by ID.

### Task Log

```bash
ak tasks log <name-or-id> [--error]
```

Show the stdout log for a task. Use `--error` for the stderr log.

Log files are stored at `~/.agent-kit/tasks/logs/<name>-<id>.log` and
`<name>-<id>.error.log`.

### Cancel a Task

```bash
ak tasks cancel <name-or-id>
```

Cancel a pending or running task. Running tasks are terminated on the next `run`
invocation's poll cycle.

### Execute Pending Tasks

```bash
ak tasks run
```

Claims all pending tasks and executes them in parallel (up to 4 concurrent). This is
the cron entry point — multiple concurrent `run` invocations are safe (atomic claiming
prevents double-execution).

Each invocation also checks for orphaned running tasks (from a previous crashed `run`)
and marks them as timed out if their logs are stale.

### Clean Up Old Tasks

```bash
ak tasks clean [--before <duration>]
```

Remove completed tasks (done, failed, timeout, cancelled) and their log files.
Default removes tasks finished more than 7 days ago.

Duration format: `<N><unit>` — `m` (minutes), `h` (hours), `d` (days).

```bash
ak tasks clean --before 1d    # remove tasks finished over 1 day ago
ak tasks clean --before 2h    # remove tasks finished over 2 hours ago
```

## Configuration

In `~/.agent-kit/config.yaml`:

```yaml
tasks:
  inactivity_timeout: 600  # seconds (default: 10 minutes)
```

The inactivity timeout controls how long a task can run without producing stdout output
before being killed. Tasks that produce no output (unlikely for kiro-cli headless) will
be killed after this period.

## Timeout Behaviour

- While running, each task's stdout log file mtime is monitored
- If no output for `inactivity_timeout` seconds, the task receives SIGTERM
- After a 10-second grace period, SIGKILL is sent if the process hasn't exited
- The task is marked as `timeout` with an error message

## Task Naming

Task names must be unique among active tasks. Once a task completes (any terminal status),
the name can be reused. This prevents accidentally running duplicate tasks while allowing
repeated execution of the same logical task.
