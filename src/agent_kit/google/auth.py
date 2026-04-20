"""Google OAuth token management with auto-refresh."""

import sys
from datetime import UTC, datetime

from agent_kit.auth import get_field, set_fields
from agent_kit.config import load_config
from agent_kit.errors import AuthError, ConfigError

_cached_token: str | None = None


def get_token() -> str:
    """Get a valid Google access token, refreshing if expired."""
    global _cached_token
    if _cached_token:
        return _cached_token

    token = get_field("google", "access_token")
    if not token:
        raise AuthError("no Google credentials — run 'ak auth login google'")

    expires_at = get_field("google", "expires_at")
    if expires_at and _is_expired(expires_at):
        token = _refresh()

    _cached_token = token
    return token


def require_service(service: str) -> None:
    """Check that a Google service is enabled in config."""
    config = load_config()
    enabled = config.get("google", {}).get(service, {}).get("enabled", True)
    if not enabled:
        raise ConfigError(f"Google {service} is disabled in config")


def _is_expired(expires_at: str) -> bool:
    """Check if token is expired or within 60s of expiry."""
    try:
        expiry = datetime.fromisoformat(expires_at)
        now = datetime.now(UTC)
        return (expiry - now).total_seconds() < 60
    except (ValueError, TypeError):
        return True


def _refresh() -> str:
    """Refresh the access token using the refresh token."""
    global _cached_token
    _cached_token = None
    from agent_kit.auth.oauth import refresh_token

    config = load_config()
    auth_config = config.get("auth", {}).get("google", {})

    token_endpoint = auth_config.get("token_endpoint")
    client_id = get_field("google", "client_id")
    client_secret = get_field("google", "client_secret")
    refresh = get_field("google", "refresh_token")

    if not all([token_endpoint, client_id, refresh]):
        raise AuthError("missing Google OAuth config or refresh token — run 'ak auth login google'")

    print("Refreshing Google token...", file=sys.stderr)
    tokens = refresh_token(token_endpoint, client_id, refresh, client_secret=client_secret)

    token_data = {"access_token": tokens["access_token"]}
    if "refresh_token" in tokens:
        token_data["refresh_token"] = tokens["refresh_token"]
    if "expires_in" in tokens:
        expires_at = datetime.now(UTC).timestamp() + tokens["expires_in"]
        token_data["expires_at"] = datetime.fromtimestamp(expires_at, UTC).isoformat()

    try:
        set_fields("google", token_data)
    except OSError:
        print("Warning: could not persist refreshed token (read-only filesystem)", file=sys.stderr)

    _cached_token = tokens["access_token"]
    return tokens["access_token"]
