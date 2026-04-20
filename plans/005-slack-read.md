# Agent Kit — Slack Read Integration

## Objective

Add read capabilities to the existing `ak slack` module. Channel history, thread
replies, message search, channel listing, and user lookup via Slack Web API using
a user OAuth token (PKCE flow). Existing webhook-based `send` command preserved.

## Requirements

### Auth

- MUST add Slack as an OAuth provider with PKCE support
  - AC: `ak auth login slack` runs OAuth + PKCE flow via browser
  - AC: Stores `user_token` (xoxp-), `refresh_token`, `expires_at`
  - AC: Slack OAuth endpoints: authorize at `https://slack.com/oauth/v2/authorize`,
    token at `https://slack.com/api/oauth.v2.access`
  - AC: User token scopes requested: `channels:history`, `channels:read`,
    `groups:history`, `groups:read`, `users:read`, `search:read`,
    `im:history`, `mpim:history`
  - AC: `client_id` and `client_secret` stored in credential store
  - AC: Existing `webhook_url` credential preserved for `send` command

### Channels

- MUST support listing channels: `ak slack channels [--limit N]`
  - AC: Returns JSON list with id, name, type (public/private/dm/group_dm), member_count
  - AC: Respects config gating (include_dms, include_group_dms)
  - AC: Default limit 100

### History

- MUST support reading channel messages: `ak slack history <channel> [--limit N] [--since HOURS]`
  - AC: `<channel>` accepts `#name`, `@user` (DMs if enabled), or channel ID
  - AC: User IDs resolved to display names in output
  - AC: Default --since 24 hours, default --limit 50
  - AC: Returns JSON list with ts, user (display name), text, thread_ts, reply_count
  - AC: Respects channel scope config

### Threads

- MUST support reading thread replies: `ak slack thread <channel> <thread-ts>`
  - AC: Returns JSON list of replies with same format as history
  - AC: Respects channel scope config

### Search

- MUST support searching messages: `ak slack search <query> [--limit N]`
  - AC: Slack search syntax passed through (from:, in:, after:, etc.)
  - AC: Always sorted by timestamp (not relevance)
  - AC: Returns JSON list with channel, ts, user, text, permalink
  - AC: Default limit 20

### Users

- MUST support listing/searching users: `ak slack users [query] [--limit N]`
  - AC: Without query, lists all users (from cache)
  - AC: With query, filters by display name, real name, or username (case-insensitive partial)
  - AC: Returns JSON list with id, name, real_name, display_name, email
  - AC: User list cached in memory for the session

### Config

- MUST support read/write gating and channel scoping
  - AC: Config structure:
    ```yaml
    slack:
      read:
        enabled: true
        scope:
          channels: []
          include_dms: false
          include_group_dms: false
      write:
        enabled: true
    ```
  - AC: Empty channels list = all channels user is in
  - AC: Non-empty channels list = only those channels accessible
  - AC: DMs/group DMs disabled by default, require explicit opt-in

### General

- MUST follow agent-kit output conventions (JSON stdout, errors stderr, exit codes)
- MUST preserve existing `send` command unchanged

## Technical Design

### Code Structure

```
src/agent_kit/slack/
├── __init__.py
├── cli.py          # Extended with read commands alongside existing send
├── client.py       # Existing webhook client (unchanged)
├── api.py          # Slack Web API client (new — user token, conversations.*)
└── resolve.py      # Channel name → ID resolution, user ID → name cache
```

### Key Decisions

- **Separate api.py from client.py** — existing client.py is webhook-only. New api.py
  handles the Web API with user tokens. Different auth, different endpoints, different
  patterns. Keep them separate rather than merging.

- **Synchronous httpx** — same as all other modules.

- **User token auth** — `Authorization: Bearer xoxp-...` header. Token stored as
  `slack.user_token` in credentials (separate from `slack.webhook_url`).

- **Auto-refresh** — same pattern as Google. Check `expires_at`, refresh if expired.
  Slack PKCE tokens rotate — refresh returns new refresh_token.

- **Channel name resolution** — `#platform` → channel ID via `conversations.list` with
  name matching. Cache the channel list for the session. `@user` → DM channel ID via
  `conversations.open` (only if DMs enabled in config).

- **User ID resolution** — Slack messages contain `U1234` user IDs. Resolve to display
  names via `users.list` cached in memory. Batch-load on first use.

- **Search sort** — always pass `sort=timestamp&sort_dir=desc` to `search.messages`.

- **Channel scope checking** — before any history/thread read, check the channel against
  config scope. If `channels` list is non-empty, channel must be in the list. DM/group DM
  channels checked against `include_dms`/`include_group_dms` flags.

- **PKCE OAuth for Slack** — Slack requires HTTPS redirects unless PKCE is enabled on the
  app. With PKCE enabled, `http://localhost:8585/callback` works. PKCE is already
  implemented in agent-kit's OAuth module. Slack uses `oauth.v2.access` for token exchange
  (not the standard OAuth token endpoint path), so we configure the token endpoint
  explicitly. User scopes go in `user_scope` parameter (not `scope`).

- **Slack OAuth quirk** — Slack's authorize URL uses `user_scope` for user token scopes,
  not `scope` (which is for bot scopes). The `build_auth_url` function needs to support
  this via `extra_params` or a dedicated parameter.

### Auth Config

```python
"slack": {
    "type": "oauth",
    "authorization_endpoint": "https://slack.com/oauth/v2/authorize",
    "token_endpoint": "https://slack.com/api/oauth.v2.access",
    "user_scopes": [
        "channels:history", "channels:read",
        "groups:history", "groups:read",
        "users:read", "search:read",
        "im:history", "mpim:history",
    ],
    "read": {"enabled": True, "scope": {"channels": [], "include_dms": False, "include_group_dms": False}},
    "write": {"enabled": True},
},
```

⚠️ Slack uses `user_scope` parameter in the authorize URL, not `scope`. The OAuth
module's `build_auth_url` passes scopes as `scope=`. We need to handle this — either
via `extra_params` (pass `user_scope` instead of `scope`) or by adding a `scope_param`
config option. Simplest: put the scopes in `extra_params` as `user_scope` and leave
`scopes` empty.

### Cross-Repo Changes

Archie changes (separate repo): TOOLS.md, config.py credential mappings,
getting-started.md. Committed separately.

## Milestones

### 1. Slack OAuth setup and channel listing

Approach:
- Add Slack OAuth config to `DEFAULT_CONFIG` with PKCE. Slack's authorize URL uses
  `user_scope` not `scope` for user token scopes — pass via `extra_params`:
  `{"user_scope": "channels:history channels:read ..."}`. Leave `scopes` empty.
- Token exchange: Slack returns `authed_user.access_token` (not top-level `access_token`).
  The OAuth module's `exchange_code` returns the raw response — we need to extract the
  user token from `authed_user`. Handle this in the login flow or with a post-processing
  hook.
- Create `api.py` with `get_user_token()` (reads from credentials, auto-refreshes) and
  a shared `_get()` helper for Web API calls.
- Create `resolve.py` with channel list caching and name → ID resolution.
- Add `channels` command to CLI.
- Add config gating (read.enabled, scope.channels, include_dms, include_group_dms).
- ⚠️ Slack's `conversations.list` requires pagination (cursor-based) for workspaces
  with many channels. Implement cursor pagination.
- ⚠️ Slack token exchange response shape differs from standard OAuth — user token is
  nested under `authed_user`, not at the top level.

Tasks:
- Add Slack OAuth config to `DEFAULT_CONFIG` in config.py
- Add Slack read/write gating config
- Handle Slack's non-standard token response in auth CLI (extract `authed_user.access_token`)
- Create `api.py` with token getter, auto-refresh, and shared `_get()` helper
- Create `resolve.py` with channel list cache and name resolution
- Add `channels` command to CLI with config gating
- Add scope checking helper

Deliverable: `ak auth login slack` completes OAuth flow. `ak slack channels` returns
channel list.

Verify: `ak slack channels` outputs JSON. Channel names and IDs are correct.

### 2. History, threads, and user resolution

Approach:
- `conversations.history` for channel messages, `conversations.replies` for threads.
  Both return messages with `user` as ID — resolve via cached user list.
- User cache: call `users.list` once (paginated), cache in memory. Resolve IDs to
  display names. Fall back to username if no display name.
- `--since` converts hours to a Unix timestamp for the `oldest` API parameter.
- Channel scope checking before any read operation.
- ⚠️ `conversations.history` returns newest first by default. Reverse for chronological
  output.

Tasks:
- Implement user list caching and ID → name resolution in resolve.py
- Implement `history` command with --limit and --since
- Implement `thread` command
- Add channel scope checking to both commands
- Resolve user IDs to display names in message output

Deliverable: `ak slack history #platform --since 24` returns recent messages with
resolved user names.

Verify: History returns chronological messages. User names are resolved. Thread
replies load correctly.

### 3. Search and users commands

Approach:
- `search.messages` API with `sort=timestamp&sort_dir=desc`. Returns matches with
  channel info and permalink.
- `users` command uses the cached user list with optional query filter (partial match
  on name, real_name, display_name).
- ⚠️ `search.messages` is not available with bot tokens — user token required (which
  we have).

Tasks:
- Implement `search` command with Slack query passthrough and timestamp sort
- Implement `users` command with optional query filter
- Add --limit to both

Deliverable: `ak slack search "from:jane aurora"` returns matching messages sorted
by date. `ak slack users "simon"` returns filtered user list.

Verify: Search returns results sorted by timestamp. User filter matches partial names.

### 4. Documentation and Archie integration

Approach:
- Update existing `docs/slack.md` to cover both webhook send and new read commands.
- Archie-side changes in separate repo.
- Bump agent-kit to 0.9.0.

Tasks:
- Update `docs/slack.md` with full read command reference
- Update agent-kit `README.md` Slack description
- Update agent-kit `CONTRIBUTING.md` module listing
- Bump agent-kit to 0.9.0 in `pyproject.toml` and `__init__.py`
- Add Slack OAuth credential mappings to Archie's `src/archie/config.py`
- Update Archie's `persona/guidance/TOOLS.md` with Slack read commands
- Update Archie's `docs/getting-started.md` with Slack OAuth setup

Deliverable: All docs updated. Version bumped.

Verify: `ak slack --help` shows all commands. Docs have complete reference.
