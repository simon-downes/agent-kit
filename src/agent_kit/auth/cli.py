"""Auth CLI commands."""

import os
import secrets
import sys
from datetime import UTC, datetime
from importlib.resources import as_file, files

import click
import yaml

from agent_kit.auth import get_field, load_credentials, set_field, set_fields


@click.group()
def auth() -> None:
    """Manage credentials for services."""


@auth.command(name="set")
@click.argument("service")
@click.argument("fields", nargs=-1, required=True)
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
                print(f"Error: no value provided for {service}.{field}", file=sys.stderr)
                sys.exit(1)

        set_field(service, field, value)

    click.echo(f"Stored {len(fields)} field(s) for {service}")


@auth.command(name="import")
@click.argument("service")
@click.argument("env_vars", nargs=-1, required=True)
def import_cmd(service: str, env_vars: tuple[str, ...]) -> None:
    """Import credentials from environment variables.

    Field names are lowercased env var names with optional service prefix stripped.
    """
    missing = [v for v in env_vars if v not in os.environ]
    if missing:
        print(f"Error: missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    for var in env_vars:
        field = var.lower()
        prefix = f"{service.lower()}_"
        if field.startswith(prefix):
            field = field[len(prefix) :]
        set_field(service, field, os.environ[var])

    click.echo(f"Imported {len(env_vars)} field(s) for {service}")


@auth.command(name="login")
@click.argument("service")
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
    from agent_kit.config import load_raw_config, save_config

    raw_config = load_raw_config()
    auth_config = raw_config.get("auth", {}).get(service, {})

    if auth_config.get("type") != "oauth":
        print(f"Error: {service} is not an OAuth provider", file=sys.stderr)
        sys.exit(1)

    redirect_uri = f"http://localhost:{CALLBACK_PORT}/callback"

    # Discover endpoints if not in config
    if "token_endpoint" not in auth_config:
        server_url = auth_config.get("server_url")
        if not server_url:
            server_url = _lookup_provider(service)

        if not server_url:
            print(f"Error: no server_url configured for {service}", file=sys.stderr)
            sys.exit(1)

        click.echo("Discovering OAuth endpoints...")
        try:
            metadata = discover_endpoints(server_url)
            auth_config["authorization_endpoint"] = metadata["authorization_endpoint"]
            auth_config["token_endpoint"] = metadata["token_endpoint"]
            if "registration_endpoint" in metadata:
                auth_config["registration_endpoint"] = metadata["registration_endpoint"]
        except Exception as e:
            print(f"Error: failed to discover endpoints: {e}", file=sys.stderr)
            sys.exit(1)

    # Register client if needed
    if "client_id" not in auth_config:
        reg_endpoint = auth_config.get("registration_endpoint")
        if not reg_endpoint:
            print(f"Error: no client_id or registration_endpoint for {service}", file=sys.stderr)
            sys.exit(1)

        click.echo("Registering OAuth client...")
        try:
            client_data = register_client(reg_endpoint, redirect_uri)
            auth_config["client_id"] = client_data["client_id"]
        except Exception as e:
            print(f"Error: client registration failed: {e}", file=sys.stderr)
            sys.exit(1)

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
        click.echo(f"\nOpen this URL in your browser:\n{auth_url}\n")

    click.echo("Waiting for authentication...")
    code, returned_state, error = wait_for_callback()

    if error:
        print(f"Error: authentication failed: {error}", file=sys.stderr)
        sys.exit(1)

    if not code:
        print("Error: authentication timed out", file=sys.stderr)
        sys.exit(1)

    if returned_state != state:
        print("Error: state mismatch — possible CSRF attack", file=sys.stderr)
        sys.exit(1)

    try:
        tokens = exchange_code(
            auth_config["token_endpoint"],
            auth_config["client_id"],
            code,
            verifier,
            redirect_uri,
        )
    except Exception as e:
        print(f"Error: token exchange failed: {e}", file=sys.stderr)
        sys.exit(1)

    token_data = {"access_token": tokens["access_token"]}
    if "refresh_token" in tokens:
        token_data["refresh_token"] = tokens["refresh_token"]
    if "expires_in" in tokens:
        expires_at = datetime.now(UTC).timestamp() + tokens["expires_in"]
        token_data["expires_at"] = datetime.fromtimestamp(expires_at, UTC).isoformat()
    set_fields(service, token_data)

    click.echo(f"Authenticated with {service}")


@auth.command(name="refresh")
@click.argument("service")
def refresh_cmd(service: str) -> None:
    """Refresh OAuth tokens for a service."""
    from agent_kit.auth.oauth import refresh_token
    from agent_kit.config import load_raw_config

    raw_config = load_raw_config()
    auth_config = raw_config.get("auth", {}).get(service, {})

    if auth_config.get("type") != "oauth":
        print(f"Error: {service} is not an OAuth provider", file=sys.stderr)
        sys.exit(1)

    token_endpoint = auth_config.get("token_endpoint")
    client_id = auth_config.get("client_id")
    stored_refresh = get_field(service, "refresh_token")

    if not all([token_endpoint, client_id, stored_refresh]):
        print(f"Error: missing config or refresh token for {service}", file=sys.stderr)
        sys.exit(1)

    try:
        tokens = refresh_token(token_endpoint, client_id, stored_refresh)
    except Exception as e:
        print(f"Error: token refresh failed: {e}", file=sys.stderr)
        sys.exit(1)

    token_data = {"access_token": tokens["access_token"]}
    if "refresh_token" in tokens:
        token_data["refresh_token"] = tokens["refresh_token"]
    if "expires_in" in tokens:
        expires_at = datetime.now(UTC).timestamp() + tokens["expires_in"]
        token_data["expires_at"] = datetime.fromtimestamp(expires_at, UTC).isoformat()
    set_fields(service, token_data)

    click.echo(f"Refreshed tokens for {service}")


@auth.command(name="status")
def status_cmd() -> None:
    """Show credential status for all services."""
    creds = load_credentials()
    if not creds:
        click.echo("No credentials stored")
        return

    for service, fields in creds.items():
        if not isinstance(fields, dict):
            continue
        field_names = list(fields.keys())
        expires_at = fields.get("expires_at")
        status = ""
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at)
                if datetime.now(expiry.tzinfo) > expiry:
                    status = " (expired)"
                else:
                    status = f" (expires {expires_at})"
            except (ValueError, TypeError):
                pass
        click.echo(f"{service}: {', '.join(field_names)}{status}")


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
