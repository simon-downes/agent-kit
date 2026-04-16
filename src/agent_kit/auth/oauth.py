"""OAuth2 + PKCE flow for browser-based authentication."""

import secrets
import webbrowser
from base64 import urlsafe_b64encode
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

CALLBACK_PORT = 8585
CALLBACK_TIMEOUT = 120
HTTP_TIMEOUT = 30


def generate_pkce() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge."""
    verifier = secrets.token_urlsafe(32)
    challenge = urlsafe_b64encode(sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def discover_endpoints(server_url: str) -> dict[str, Any]:
    """Discover OAuth endpoints using RFC 9470 and RFC 8414."""
    resp = httpx.get(f"{server_url}/.well-known/oauth-protected-resource", timeout=HTTP_TIMEOUT)
    resp.raise_for_status()

    auth_server_url = resp.json()["authorization_servers"][0]

    resp = httpx.get(
        f"{auth_server_url}/.well-known/oauth-authorization-server", timeout=HTTP_TIMEOUT
    )
    resp.raise_for_status()

    return resp.json()


def register_client(registration_endpoint: str, redirect_uri: str) -> dict[str, Any]:
    """Register OAuth client dynamically (RFC 7591)."""
    resp = httpx.post(
        registration_endpoint,
        json={
            "client_name": "Agent Kit",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
        headers={"Content-Type": "application/json"},
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def exchange_code(
    token_endpoint: str, client_id: str, code: str, verifier: str, redirect_uri: str
) -> dict[str, Any]:
    """Exchange authorization code for tokens."""
    resp = httpx.post(
        token_endpoint,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_token(token_endpoint: str, client_id: str, refresh: str) -> dict[str, Any]:
    """Refresh access token using refresh token."""
    resp = httpx.post(
        token_endpoint,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": client_id,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def build_auth_url(
    authorization_endpoint: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    challenge: str,
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
    return f"{authorization_endpoint}?{urlencode(params)}"


def open_browser(url: str) -> bool:
    """Open URL in browser. Returns False if it fails."""
    try:
        return webbrowser.open(url)
    except Exception:
        return False


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    auth_code: str | None = None
    auth_state: str | None = None
    auth_error: str | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)
        _CallbackHandler.auth_code = params.get("code", [None])[0]
        _CallbackHandler.auth_state = params.get("state", [None])[0]
        _CallbackHandler.auth_error = params.get("error", [None])[0]

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        if _CallbackHandler.auth_error:
            self.wfile.write(b"<h1>Authentication failed</h1><p>You can close this window.</p>")
        else:
            self.wfile.write(b"<h1>Authentication successful</h1><p>You can close this window.</p>")

    def log_message(self, format: str, *args: Any) -> None:
        pass


def wait_for_callback() -> tuple[str | None, str | None, str | None]:
    """Run callback server and return (code, state, error). Times out after CALLBACK_TIMEOUT."""
    _CallbackHandler.auth_code = None
    _CallbackHandler.auth_state = None
    _CallbackHandler.auth_error = None

    server = HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    server.timeout = CALLBACK_TIMEOUT
    server.handle_request()

    return _CallbackHandler.auth_code, _CallbackHandler.auth_state, _CallbackHandler.auth_error
