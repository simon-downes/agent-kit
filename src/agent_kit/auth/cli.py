"""Auth CLI commands."""

import os
import secrets
import sys
from datetime import UTC, datetime
from importlib.resources import as_file, files
from typing import Any

import click
import yaml

from agent_kit.auth import get_field, load_credentials, set_field, set_fields
from agent_kit.errors import AuthError, handle_errors, output


@click.group()
def auth() -> None:
    """Manage credentials for services."""


@auth.command(name="set")
@click.argument("service")
@click.argument("fields", nargs=-1, required=True)
@handle_errors
def set_cmd(service: str, fields: tuple[str, ...]) -> None:
    """Store credentials for a service.

    Prompts interactively for each value, or reads from stdin when piped.
    """
    for field in fields:
        if sys.stdin.isatty():
            value = click.prompt(f"{service}.{field}", hide_input=True)
        else:
            value = sys.stdin.readline().strip()
            if not value:
                raise ValueError(f"no value provided for {service}.{field}")

        set_field(service, field, value)

    print("OK")


@auth.command(name="import")
@click.argument("service")
@click.argument("env_vars", nargs=-1, required=True)
@handle_errors
def import_cmd(service: str, env_vars: tuple[str, ...]) -> None:
    """Import credentials from environment variables.

    Field names are lowercased env var names with optional service prefix stripped.
    """
    missing = [v for v in env_vars if v not in os.environ]
    if missing:
        raise ValueError(f"missing environment variables: {', '.join(missing)}")

    for var in env_vars:
        field = var.lower()
        prefix = f"{service.lower()}_"
        if field.startswith(prefix):
            field = field[len(prefix) :]
        set_field(service, field, os.environ[var])

    print("OK")


@auth.command(name="login")
@click.argument("service")
@handle_errors
def login_cmd(service: str) -> None:
    """Authenticate with an OAuth service via browser."""
    from agent_kit.auth.oauth import (
        CALLBACK_PORT,
        build_auth_url,
        discover_endpoints,
        exchange_code,
        generate_pkce,
        open_browser,
        register_client,
        wait_for_callback,
    )
    from agent_kit.config import load_config, save_config

    raw_config = load_config()
    auth_config = raw_config.get("auth", {}).get(service, {})

    if auth_config.get("type") != "oauth":
        raise AuthError(f"{service} is not an OAuth provider")

    redirect_uri = f"http://localhost:{CALLBACK_PORT}/callback"

    # Discover endpoints if not in config
    if "token_endpoint" not in auth_config:
        server_url = auth_config.get("server_url")
        if not server_url:
            server_url = _lookup_provider(service)

        if not server_url:
            raise AuthError(f"no server_url configured for {service}")

        click.echo("Discovering OAuth endpoints...", err=True)
        metadata = discover_endpoints(server_url)
        auth_config["authorization_endpoint"] = metadata["authorization_endpoint"]
        auth_config["token_endpoint"] = metadata["token_endpoint"]
        if "registration_endpoint" in metadata:
            auth_config["registration_endpoint"] = metadata["registration_endpoint"]

    # Register client if needed
    if "client_id" not in auth_config:
        reg_endpoint = auth_config.get("registration_endpoint")
        if not reg_endpoint:
            raise AuthError(f"no client_id or registration_endpoint for {service}")

        click.echo("Registering OAuth client...", err=True)
        client_data = register_client(reg_endpoint, redirect_uri)
        auth_config["client_id"] = client_data["client_id"]

    # Write discovered config back
    raw_config.setdefault("auth", {})[service] = auth_config
    save_config(raw_config)

    # Run OAuth flow
    verifier, challenge = generate_pkce()
    state = secrets.token_urlsafe(16)

    auth_url = build_auth_url(
        auth_config["authorization_endpoint"],
        auth_config["client_id"],
        redirect_uri,
        state,
        challenge,
    )

    if not open_browser(auth_url):
        click.echo(f"\nOpen this URL in your browser:\n{auth_url}\n", err=True)

    click.echo("Waiting for authentication...", err=True)
    code, returned_state, error = wait_for_callback()

    if error:
        raise AuthError(f"authentication failed: {error}")

    if not code:
        raise AuthError("authentication timed out")

    if returned_state != state:
        raise AuthError("state mismatch — possible CSRF attack")

    tokens = exchange_code(
        auth_config["token_endpoint"],
        auth_config["client_id"],
        code,
        verifier,
        redirect_uri,
    )

    token_data = {"access_token": tokens["access_token"]}
    if "refresh_token" in tokens:
        token_data["refresh_token"] = tokens["refresh_token"]
    if "expires_in" in tokens:
        expires_at = datetime.now(UTC).timestamp() + tokens["expires_in"]
        token_data["expires_at"] = datetime.fromtimestamp(expires_at, UTC).isoformat()
    set_fields(service, token_data)

    print("OK")


@auth.command(name="refresh")
@click.argument("service")
@handle_errors
def refresh_cmd(service: str) -> None:
    """Refresh OAuth tokens for a service."""
    from agent_kit.auth.oauth import refresh_token
    from agent_kit.config import load_config

    raw_config = load_config()
    auth_config = raw_config.get("auth", {}).get(service, {})

    if auth_config.get("type") != "oauth":
        raise AuthError(f"{service} is not an OAuth provider")

    token_endpoint = auth_config.get("token_endpoint")
    client_id = auth_config.get("client_id")
    stored_refresh = get_field(service, "refresh_token")

    if not all([token_endpoint, client_id, stored_refresh]):
        raise AuthError(f"missing config or refresh token for {service}")

    tokens = refresh_token(token_endpoint, client_id, stored_refresh)

    token_data = {"access_token": tokens["access_token"]}
    if "refresh_token" in tokens:
        token_data["refresh_token"] = tokens["refresh_token"]
    if "expires_in" in tokens:
        expires_at = datetime.now(UTC).timestamp() + tokens["expires_in"]
        token_data["expires_at"] = datetime.fromtimestamp(expires_at, UTC).isoformat()
    set_fields(service, token_data)

    print("OK")


@auth.command(name="status")
@handle_errors
def status_cmd() -> None:
    """Show credential status for all services."""
    creds = load_credentials()
    services = {}
    for service, fields in creds.items():
        if not isinstance(fields, dict):
            continue
        info: dict[str, Any] = {"fields": list(fields.keys())}
        expires_at = fields.get("expires_at")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at)
                info["expires_at"] = expires_at
                info["expired"] = datetime.now(expiry.tzinfo) > expiry
            except (ValueError, TypeError):
                pass
        services[service] = info
    output(services)


def _lookup_provider(service: str) -> str | None:
    """Look up a provider's server_url from bundled providers.yaml."""
    try:
        providers_pkg = files("agent_kit").joinpath("auth", "providers.yaml")
        with as_file(providers_pkg) as p:
            providers = yaml.safe_load(p.read_text())
        provider = providers.get("providers", {}).get(service)
        if provider:
            return provider.get("server_url")
    except Exception:
        pass
    return None
