# Slack

Read channels, search messages, and send notifications via Slack.

## Credentials

Two auth mechanisms for different use cases:

**Read access** — requires a Slack app with user token (PKCE OAuth):

```bash
ak auth set slack client_id
ak auth set slack client_secret
ak auth login slack
```

**Write access** — uses an incoming webhook (existing):

```bash
ak auth set slack webhook_url
```

### App Setup

1. Create an internal Slack app at https://api.slack.com/apps
2. Enable PKCE under OAuth & Permissions
3. Add `http://localhost:8585/callback` as redirect URL
4. Add user token scopes: `channels:history`, `channels:read`, `groups:history`,
   `groups:read`, `users:read`, `search:read`, `im:history`, `mpim:history`
5. Store client_id and client_secret, then run `ak auth login slack`

## Read Commands

### `ak slack channels`

List channels you're in.

```bash
ak slack channels
ak slack channels --limit 20
```

### `ak slack history <channel>`

Read recent messages from a channel. Accepts `#name`, `@user` (DMs if enabled),
or channel ID.

```bash
ak slack history "#platform"
ak slack history "#platform" --since 8 --limit 20
ak slack history C1234567890
```

| Option | Description |
|--------|-------------|
| `--since N` | Hours to look back (default: 24) |
| `--limit N` | Maximum messages (default: 50) |

### `ak slack thread <channel> <thread-ts>`

Read thread replies.

```bash
ak slack thread "#platform" 1776709000.123456
```

### `ak slack search <query>`

Search messages using Slack query syntax. Always sorted by date (newest first).

```bash
ak slack search "aurora failover"
ak slack search "from:jane in:#platform after:2026-04-01"
```

| Option | Description |
|--------|-------------|
| `--limit N` | Maximum results (default: 20) |

### `ak slack users [query]`

List or search workspace users.

```bash
ak slack users
ak slack users "simon"
ak slack users --limit 10
```

## Write Commands

### `ak slack send`

Send a message via incoming webhook. Supports mrkdwn formatting.

```bash
ak slack send "Deploy complete :white_check_mark:"
ak slack send "All checks passed" --header "Deploy Complete" --field "App=my-app"
echo "Build finished" | ak slack send
echo '{"text":"fallback","blocks":[...]}' | ak slack send --json
```

## Config

```yaml
slack:
  read:
    enabled: true
    scope:
      channels: []           # empty = all channels you're in
      include_dms: false     # DMs disabled by default
      include_group_dms: false
  write:
    enabled: true
```

When `channels` has entries, only those channels are accessible for read operations.
DMs and group DMs require explicit opt-in.
