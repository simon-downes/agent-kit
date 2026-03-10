"""OAuth flow implementation."""

import secrets
from base64 import urlsafe_b64encode
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx


def base64url_encode(data: bytes) -> str:
    """Encode bytes as base64url without padding."""
    return urlsafe_b64encode(data).decode().rstrip("=")


def generate_pkce() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge."""
    verifier = secrets.token_urlsafe(32)
    challenge = base64url_encode(sha256(verifier.encode()).digest())
    return verifier, challenge


def discover_oauth_metadata(server_url: str) -> dict[str, Any]:
    """Discover OAuth endpoints using RFC 9470 and RFC 8414."""
    protected_resource_url = f"{server_url}/.well-known/oauth-protected-resource"
    resp = httpx.get(protected_resource_url)
    resp.raise_for_status()

    auth_servers = resp.json()["authorization_servers"]
    auth_server_url = auth_servers[0]

    metadata_url = f"{auth_server_url}/.well-known/oauth-authorization-server"
    resp = httpx.get(metadata_url)
    resp.raise_for_status()

    return resp.json()  # type: ignore[no-any-return]


def register_client(
    registration_endpoint: str, redirect_uri: str, client_name: str = "CLI OAuth Client"
) -> dict[str, Any]:
    """Register OAuth client dynamically (RFC 7591)."""
    registration_data = {
        "client_name": client_name,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }

    resp = httpx.post(
        registration_endpoint,
        json=registration_data,
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()

    return resp.json()  # type: ignore[no-any-return]


def exchange_code_for_tokens(
    token_endpoint: str,
    client_id: str,
    code: str,
    verifier: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Exchange authorization code for access and refresh tokens."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }

    resp = httpx.post(
        token_endpoint,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()

    return resp.json()  # type: ignore[no-any-return]


def revoke_token(revocation_endpoint: str, token: str, client_id: str) -> bool:
    """Revoke an OAuth token. Returns True if successful."""
    data = {"token": token, "client_id": client_id}

    try:
        resp = httpx.post(
            revocation_endpoint,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return resp.is_success  # type: ignore[no-any-return]
    except Exception:
        return False


def refresh_access_token(token_endpoint: str, client_id: str, refresh_token: str) -> dict[str, Any]:
    """Refresh access token using refresh token."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }

    resp = httpx.post(
        token_endpoint,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()

    return resp.json()  # type: ignore[no-any-return]


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    auth_code: str | None = None
    auth_state: str | None = None
    auth_error: str | None = None

    def do_GET(self) -> None:
        """Handle GET request to callback endpoint."""
        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            params = parse_qs(parsed.query)
            CallbackHandler.auth_code = params.get("code", [None])[0]
            CallbackHandler.auth_state = params.get("state", [None])[0]
            CallbackHandler.auth_error = params.get("error", [None])[0]

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            if CallbackHandler.auth_error:
                self.wfile.write(
                    b"<h1>Authentication failed!</h1><p>You can close this window.</p>"
                )
            else:
                self.wfile.write(
                    b"<h1>Authentication successful!</h1><p>You can close this window.</p>"
                )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress log messages."""
        pass


def run_callback_server(port: int) -> tuple[str | None, str | None, str | None]:
    """Run callback server and return (code, state, error)."""
    CallbackHandler.auth_code = None
    CallbackHandler.auth_state = None
    CallbackHandler.auth_error = None

    server = HTTPServer(("localhost", port), CallbackHandler)
    server.handle_request()

    return CallbackHandler.auth_code, CallbackHandler.auth_state, CallbackHandler.auth_error


def build_authorization_url(
    authorization_endpoint: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    challenge: str,
    extra_params: dict[str, str] | None = None,
) -> str:
    """Build OAuth authorization URL."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }

    if extra_params:
        params.update(extra_params)

    return f"{authorization_endpoint}?{urlencode(params)}"
