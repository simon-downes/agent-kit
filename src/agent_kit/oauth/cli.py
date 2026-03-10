"""CLI interface for oauth tool."""

import json
import os
import secrets
import sys
import webbrowser

import click
from rich.console import Console

from agent_kit.kv import db
from agent_kit.oauth.flow import (
    build_authorization_url,
    exchange_code_for_tokens,
    generate_pkce,
    register_client,
    revoke_token,
    run_callback_server,
)
from agent_kit.oauth.provider import get_provider_config, get_provider_endpoints, load_providers

console = Console()


@click.group()
def main() -> None:
    """OAuth - Authenticate with SaaS providers."""
    pass


@main.command("list")
def list_providers() -> None:
    """List configured providers and authentication status."""
    from rich.table import Table

    providers = load_providers()

    table = Table(show_header=True)
    table.add_column("Provider")
    table.add_column("Status")

    for provider_id in providers:
        kv_key = f"oauth-{provider_id}"
        token_json = db.get(kv_key)

        status = "[green]✓ Authenticated[/green]" if token_json else "[dim]Not authenticated[/dim]"

        table.add_row(provider_id, status)

    console.print(table)


@main.command()
@click.argument("provider")
@click.option("--headless", is_flag=True, help="Don't open browser automatically")
def login(provider: str, headless: bool) -> None:
    """Authenticate with a provider."""
    try:
        config = get_provider_config(provider)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    port = int(os.environ.get("OAUTH_LOCAL_PORT", "3000"))
    redirect_uri = f"http://localhost:{port}/callback"

    try:
        console.print(f"🔍 Discovering OAuth endpoints for {config.get('name', provider)}...")
        endpoints = get_provider_endpoints(config)

        if not endpoints.get("registration_endpoint"):
            console.print("[red]Error:[/red] Provider does not support dynamic client registration")
            sys.exit(1)

        console.print("📝 Registering OAuth client...")
        client_creds = register_client(
            endpoints["registration_endpoint"],
            redirect_uri,
            f"{config.get('name', provider)} CLI",
        )
        client_id = client_creds["client_id"]

        console.print("🔐 Generating PKCE parameters...")
        verifier, challenge = generate_pkce()
        state = secrets.token_urlsafe(32)

        auth_url = build_authorization_url(
            endpoints["authorization_endpoint"],
            client_id,
            redirect_uri,
            state,
            challenge,
            config.get("auth_params"),
        )

        console.print(f"\n🌐 Authorization URL: {auth_url}")
        if not headless:
            console.print("Opening browser...")
            webbrowser.open(auth_url)
        else:
            console.print("Please visit the URL above to authorize.\n")

        console.print(f"⏳ Waiting for callback on port {port}...")
        code, callback_state, error = run_callback_server(port)

        if error:
            console.print(f"[red]❌ Authorization failed:[/red] {error}")
            sys.exit(1)

        if not code:
            console.print("[red]❌ No authorization code received[/red]")
            sys.exit(1)

        if callback_state != state:
            console.print("[red]❌ State mismatch - possible CSRF attack[/red]")
            sys.exit(1)

        console.print("✅ Authorization code received")
        console.print("🔄 Exchanging code for tokens...")

        tokens = exchange_code_for_tokens(
            endpoints["token_endpoint"], client_id, code, verifier, redirect_uri
        )

        token_data = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "token_type": tokens["token_type"],
            "expires_in": tokens.get("expires_in"),
            "client_id": client_id,
            "token_endpoint": endpoints["token_endpoint"],
            "revocation_endpoint": endpoints.get("revocation_endpoint"),
        }

        kv_key = f"oauth-{provider}"
        db.set(kv_key, json.dumps(token_data))

        console.print(f"\n✅ Tokens saved to kv store (key: [cyan]{kv_key}[/cyan])")
        console.print("🎉 Authentication complete!")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("provider")
def logout(provider: str) -> None:
    """Logout from a provider (revoke tokens and remove from kv)."""
    kv_key = f"oauth-{provider}"

    token_json = db.get(kv_key)
    if not token_json:
        console.print(f"[yellow]Not authenticated with {provider}[/yellow]")
        return

    try:
        token_data = json.loads(token_json)

        if token_data.get("revocation_endpoint") and token_data.get("access_token"):
            console.print("🔄 Revoking tokens...")
            success = revoke_token(
                token_data["revocation_endpoint"],
                token_data["access_token"],
                token_data["client_id"],
            )
            if success:
                console.print("✅ Tokens revoked")
            else:
                console.print("[yellow]⚠️  Token revocation failed (continuing anyway)[/yellow]")

        db.delete(kv_key)
        console.print("✅ Removed credentials from kv store")
        console.print(f"🎉 Logged out from {provider}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("provider")
def status(provider: str) -> None:
    """Check authentication status for a provider."""
    kv_key = f"oauth-{provider}"

    token_json = db.get(kv_key)
    if not token_json:
        console.print(f"[yellow]Not authenticated with {provider}[/yellow]")
        sys.exit(1)

    try:
        token_data = json.loads(token_json)

        console.print(f"[green]✓[/green] Authenticated with {provider}")
        console.print(f"\nToken type: {token_data.get('token_type', 'unknown')}")

        if token_data.get("expires_in"):
            console.print(f"Expires in: {token_data['expires_in']} seconds")

        if token_data.get("refresh_token"):
            console.print("Refresh token: [green]available[/green]")
        else:
            console.print("Refresh token: [yellow]not available[/yellow]")

        console.print(f"\nStored in kv: [cyan]{kv_key}[/cyan]")

    except json.JSONDecodeError:
        console.print("[red]Error:[/red] Invalid token data in kv store")
        sys.exit(1)


@main.command()
@click.argument("provider")
def refresh(provider: str) -> None:
    """Refresh access token using refresh token."""
    from agent_kit.oauth.flow import refresh_access_token

    kv_key = f"oauth-{provider}"

    token_json = db.get(kv_key)
    if not token_json:
        console.print(f"[red]Error:[/red] Not authenticated with {provider}")
        console.print("\nRun: [cyan]uvx oauth login {provider}[/cyan]")
        sys.exit(2)

    try:
        token_data = json.loads(token_json)

        if not token_data.get("refresh_token"):
            console.print("[red]Error:[/red] No refresh token available")
            console.print("\nYou need to re-authenticate:")
            console.print(f"[cyan]uvx oauth login {provider}[/cyan]")
            sys.exit(2)

        if not token_data.get("token_endpoint"):
            console.print("[red]Error:[/red] Token endpoint not found in stored credentials")
            sys.exit(2)

        console.print("🔄 Refreshing access token...")

        new_tokens = refresh_access_token(
            token_data["token_endpoint"],
            token_data["client_id"],
            token_data["refresh_token"],
        )

        # Update stored credentials with new access token
        token_data["access_token"] = new_tokens["access_token"]
        if "expires_in" in new_tokens:
            token_data["expires_in"] = new_tokens["expires_in"]
        # Some providers issue new refresh tokens
        if "refresh_token" in new_tokens:
            token_data["refresh_token"] = new_tokens["refresh_token"]

        db.set(kv_key, json.dumps(token_data))

        console.print(f"✅ Access token refreshed for {provider}")

    except json.JSONDecodeError:
        console.print("[red]Error:[/red] Invalid token data in kv store")
        sys.exit(2)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to refresh token: {e}")
        console.print("\nYou may need to re-authenticate:")
        console.print(f"[cyan]uvx oauth login {provider}[/cyan]")
        sys.exit(2)


@main.command()
@click.argument("provider")
def show(provider: str) -> None:
    """Show stored tokens for a provider."""
    kv_key = f"oauth-{provider}"

    token_json = db.get(kv_key)
    if not token_json:
        sys.exit(2)

    print(token_json)


if __name__ == "__main__":
    main()
