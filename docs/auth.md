# Auth

Credential management for all agent-kit services. Supports static tokens and OAuth2 with
PKCE for browser-based authentication.

Credentials are stored in `~/.agent-kit/credentials.yaml` (mode 0600).

## Commands

### `ak auth set <service> <field> [<field>...]`

Store credentials interactively. Prompts for each value (hidden input). Reads from stdin
when piped.

```bash
# Interactive
ak auth set github token
ak auth set aws access_key_id secret_access_key session_token

# Piped
echo "ghp_xxx" | ak auth set github token
```

### `ak auth import <service> <ENV_VAR> [<ENV_VAR>...]`

Import credentials from environment variables. Field names are derived by lowercasing the
variable name and stripping the service prefix.

```bash
# AWS_ACCESS_KEY_ID → access_key_id, AWS_SECRET_ACCESS_KEY → secret_access_key
aws-vault exec my-profile -- ak auth import aws \
  AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
```

### `ak auth login <service>`

OAuth2 + PKCE browser-based authentication. Discovers endpoints automatically, registers
a client if needed, opens the browser, and stores the resulting tokens.

```bash
ak auth login notion
```

On first login, discovered endpoints and client ID are written back to
`~/.agent-kit/config.yaml` for reuse.

### `ak auth refresh <service>`

Manually refresh OAuth tokens using the stored refresh token.

```bash
ak auth refresh notion
```

### `ak auth status`

Show credential status for all stored services. Outputs JSON with field names and
expiry information.

```bash
ak auth status
ak auth status | jq '.notion'
```

## Configuration

Auth provider types are defined in `~/.agent-kit/config.yaml` under the `auth` key.
Defaults are provided for common services:

```yaml
auth:
  notion:
    type: oauth
  linear:
    type: static
    fields: [token]
  slack:
    type: static
    fields: [webhook_url]
  github:
    type: static
    fields: [token]
  aws:
    type: static
    fields: [access_key_id, secret_access_key, session_token]
  scalr:
    type: static
    fields: [token, hostname]
```

OAuth providers gain additional fields after first login:

```yaml
auth:
  notion:
    type: oauth
    authorization_endpoint: "https://..."
    token_endpoint: "https://..."
    client_id: "..."
```

## Adding a New Provider

Static providers need no code — add the service to the `auth` section of `DEFAULT_CONFIG`
in `config.py` with `type: static` and `fields`.

OAuth providers also need an entry in `src/agent_kit/auth/providers.yaml` with a
`server_url` for endpoint discovery.
