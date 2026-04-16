# Slack

Send messages to Slack channels via incoming webhooks.

## Credentials

Requires a Slack incoming webhook URL. Resolved in order:

1. `~/.agent-kit/credentials.yaml` → `slack.webhook_url`
2. `SLACK_WEBHOOK_URL` environment variable

```bash
ak auth set slack webhook_url
```

## Commands

### `ak slack send [text]`

Send a message. Text can be provided as an argument or piped via stdin. Supports
[mrkdwn](https://api.slack.com/reference/surfaces/formatting) formatting.

```bash
# Simple text
ak slack send "Deploy complete :white_check_mark:"

# With header and fields
ak slack send "All checks passed" --header "Deploy Complete" \
  --field "App=my-app" --field "Env=prod"

# Pipe from another command
echo "Build finished" | ak slack send

# Raw Block Kit JSON from stdin
echo '{"text":"fallback","blocks":[...]}' | ak slack send --json
```

| Option | Description |
|--------|-------------|
| `--header TEXT` | Header block text |
| `--field KEY=VALUE` | Section field (repeatable) |
| `--json` | Read raw Block Kit JSON payload from stdin |

Outputs `OK` on success.

### Message Structure

Without `--json`, the message is built as Block Kit blocks:

1. **Header block** (if `--header` provided) — plain text
2. **Section block** — the message text (mrkdwn)
3. **Fields block** (if `--field` provided) — key/value pairs

With `--json`, the entire payload is sent as-is. Use this for full Block Kit control.
