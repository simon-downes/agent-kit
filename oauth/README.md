# oauth

OAuth authentication for SaaS providers.

## Purpose

`oauth` handles OAuth 2.0 authentication flows for various SaaS providers, storing credentials securely using the `kv` tool. It supports dynamic endpoint discovery and client registration for providers that implement RFC 8414 and RFC 7591.

## Features

- OAuth 2.0 with PKCE (Proof Key for Code Exchange)
- Dynamic endpoint discovery (RFC 8414)
- Dynamic client registration (RFC 7591)
- Token storage in kv tool
- Headless mode for SSH/remote scenarios
- Configurable local callback port
- Token revocation on logout

## Requirements

- `kv` tool must be installed (for token storage)
- Python 3.13+

## Installation

```bash
# Install globally
uv tool install git+https://github.com/simon-downes/cli-tools.git --subdirectory oauth

# Or run directly without installing
uvx --from git+https://github.com/simon-downes/cli-tools.git --subdirectory oauth oauth --help
```

## Usage

### Authenticate with a Provider

```bash
# Interactive mode (opens browser)
oauth login notion

# Headless mode (prints URL, doesn't open browser)
oauth login notion --headless
```

The OAuth flow:
1. Discovers OAuth endpoints from provider
2. Registers a dynamic OAuth client
3. Opens browser for authorization (or prints URL in headless mode)
4. Receives callback with authorization code
5. Exchanges code for access/refresh tokens
6. Stores tokens in kv as JSON (key: `oauth-notion`)

### Check Authentication Status

```bash
oauth status notion
```

Output shows:
- Authentication status
- Token type
- Token expiry (if available)
- Refresh token availability
- kv storage key

Exit codes:
- `0` - Authenticated
- `1` - Not authenticated

### Refresh Access Token

```bash
oauth refresh notion
```

Uses the stored refresh token to obtain a new access token. Useful when the access token has expired but the refresh token is still valid.

Exit codes:
- `0` - Success (token refreshed)
- `2` - Error (no refresh token, refresh failed, or not authenticated)

### Show Stored Tokens

```bash
oauth show notion
```

Outputs the raw JSON token data to stdout. Useful for piping to `jq` or other tools:

```bash
# Extract access token
ACCESS_TOKEN=$(oauth show notion | jq -r .access_token)

# Pretty print
oauth show notion | jq .
```

Exit codes:
- `0` - Success (tokens found)
- `2` - Not authenticated (no output)

### Logout

```bash
oauth logout notion
```

This will:
1. Attempt to revoke tokens at the provider (if supported)
2. Remove credentials from kv store

Logout is considered successful even if token revocation fails, as long as credentials are removed from kv.

## Configuration

### Providers Configuration

Providers are configured in `~/.cli-tools/oauth/providers.yaml`. A default configuration is created automatically on first use.

Example configuration:

```yaml
providers:
  notion:
    name: "Notion"
    server_url: "https://mcp.notion.com"
    # Optional: explicit endpoints if discovery not supported
    # authorization_endpoint: "https://..."
    # token_endpoint: "https://..."
    # registration_endpoint: "https://..."
    # revocation_endpoint: "https://..."
    # Optional: additional authorization parameters
    # auth_params:
    #   prompt: "consent"
    #   scope: "read write"
```

**Dynamic Discovery:**
If only `server_url` is provided, oauth will attempt to discover endpoints using:
- RFC 9470 (Protected Resource Metadata)
- RFC 8414 (Authorization Server Metadata)

**Explicit Endpoints:**
For providers that don't support discovery, specify endpoints explicitly.

### Environment Variables

**OAUTH_LOCAL_PORT**
- Default: `3000`
- The local port for the OAuth callback server
- Example: `OAUTH_LOCAL_PORT=8080 oauth login notion`

## Supported Providers

Currently configured providers:

- **Notion** - Dynamic discovery and registration

To add a new provider, edit `~/.cli-tools/oauth/providers.yaml` and add the provider configuration.

## Token Storage

Tokens are stored in the kv tool with the key format: `oauth-<provider>`

Example token structure:
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "client_id": "...",
  "token_endpoint": "https://...",
  "revocation_endpoint": "https://..."
}
```

You can manually inspect tokens:
```bash
kv get oauth-notion | jq .
```

## Examples

**Note:** Examples assume `oauth` is installed globally. If using `uvx`, prefix commands with:
```bash
uvx --from git+https://github.com/simon-downes/cli-tools.git --subdirectory oauth oauth <command>
```

### Basic Workflow

```bash
# Authenticate
oauth login notion

# Check status
oauth status notion
# ✓ Authenticated with notion
# Token type: Bearer
# Expires in: 3600 seconds
# Refresh token: available

# Get tokens
oauth show notion | jq .

# Use the token in your application
ACCESS_TOKEN=$(oauth show notion | jq -r .access_token)
curl -H "Authorization: Bearer $ACCESS_TOKEN" https://api.notion.com/...

# Refresh token when it expires
oauth refresh notion

# Logout when done
oauth logout notion
```

### Headless/SSH Scenario

```bash
# On remote server
oauth login notion --headless
# 🌐 Authorization URL: https://...
# Please visit the URL above to authorize.
# ⏳ Waiting for callback on port 3000...

# Copy URL and open in local browser
# After authorization, tokens are stored
```

### Custom Port

```bash
# Use different port (e.g., if 3000 is in use)
OAUTH_LOCAL_PORT=8080 oauth login notion
```

## Technical Details

### Architecture

- **CLI Framework:** click for command structure
- **HTTP Client:** httpx for OAuth API calls
- **Configuration:** YAML for provider definitions
- **Token Storage:** kv tool (SQLite-backed)
- **OAuth Flow:** Authorization Code with PKCE

### OAuth Flow Details

1. **Endpoint Discovery** (if using `server_url`):
   - Fetch `/.well-known/oauth-protected-resource` (RFC 9470)
   - Extract authorization server URL
   - Fetch `/.well-known/oauth-authorization-server` (RFC 8414)
   - Extract OAuth endpoints

2. **Client Registration** (RFC 7591):
   - POST to registration endpoint
   - Request authorization_code + refresh_token grants
   - Receive client_id (no client_secret for public clients)

3. **Authorization**:
   - Generate PKCE code_verifier and code_challenge
   - Build authorization URL with PKCE parameters
   - Open browser or print URL
   - Start local HTTP server for callback

4. **Token Exchange**:
   - Receive authorization code via callback
   - Verify state parameter (CSRF protection)
   - Exchange code for tokens using PKCE verifier
   - Store tokens in kv

### Dependencies

- `click>=8.1.0` - CLI framework
- `rich>=13.0.0` - Terminal formatting
- `httpx>=0.27.0` - HTTP client
- `pyyaml>=6.0.0` - YAML configuration

### Development

```bash
# Run tests
cd oauth && uv run pytest -v

# Type check
uv run mypy src/

# Lint and format
uv run ruff check .
uv run black .
```

### Project Structure

```
oauth/
├── pyproject.toml
├── README.md
├── src/oauth/
│   ├── __init__.py
│   ├── cli.py          # CLI commands
│   ├── flow.py         # OAuth flow implementation
│   ├── provider.py     # Provider configuration
│   └── providers.yaml  # Default provider config
└── tests/
    ├── test_flow.py     # OAuth flow tests
    └── test_provider.py # Provider config tests
```

## Limitations

- Currently only supports providers with dynamic client registration (RFC 7591)
- Pre-registered OAuth apps (with client_id/client_secret) are not yet supported
- Token refresh is not automated (tokens are stored but not automatically refreshed)

## Future Enhancements

- Support for pre-registered OAuth applications
- Automatic token refresh
- Additional providers (Google, Jira, etc.)
- Token expiry tracking in kv
