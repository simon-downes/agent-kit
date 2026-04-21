"""Tests for agent_kit.auth.oauth."""

import hashlib
from base64 import urlsafe_b64decode

import respx
from httpx import Response

from agent_kit.auth.oauth import (
    build_auth_url,
    exchange_code,
    generate_pkce,
    refresh_token,
)


class TestGeneratePkce:
    def test_returns_verifier_and_challenge(self):
        verifier, challenge = generate_pkce()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 20

    def test_challenge_is_s256_of_verifier(self):
        verifier, challenge = generate_pkce()
        expected = hashlib.sha256(verifier.encode()).digest()
        # challenge is base64url without padding
        decoded = urlsafe_b64decode(challenge + "==")
        assert decoded == expected

    def test_unique_each_call(self):
        v1, _ = generate_pkce()
        v2, _ = generate_pkce()
        assert v1 != v2


class TestExchangeCode:
    @respx.mock
    def test_exchanges_code_for_tokens(self):
        respx.post("https://auth.example.com/token").mock(
            return_value=Response(200, json={"access_token": "at", "refresh_token": "rt"})
        )
        result = exchange_code(
            "https://auth.example.com/token",
            client_id="cid",
            code="authcode",
            verifier="v",
            redirect_uri="http://localhost:8585/callback",
        )
        assert result["access_token"] == "at"
        assert result["refresh_token"] == "rt"

    @respx.mock
    def test_includes_client_secret_when_provided(self):
        route = respx.post("https://auth.example.com/token").mock(
            return_value=Response(200, json={"access_token": "at"})
        )
        exchange_code(
            "https://auth.example.com/token",
            client_id="cid",
            code="authcode",
            verifier="v",
            redirect_uri="http://localhost:8585/callback",
            client_secret="secret",
        )
        body = route.calls[0].request.content.decode()
        assert "client_secret=secret" in body

    @respx.mock
    def test_omits_client_secret_when_none(self):
        route = respx.post("https://auth.example.com/token").mock(
            return_value=Response(200, json={"access_token": "at"})
        )
        exchange_code(
            "https://auth.example.com/token",
            client_id="cid",
            code="authcode",
            verifier="v",
            redirect_uri="http://localhost:8585/callback",
        )
        body = route.calls[0].request.content.decode()
        assert "client_secret" not in body


class TestRefreshToken:
    @respx.mock
    def test_refreshes_token(self):
        respx.post("https://auth.example.com/token").mock(
            return_value=Response(200, json={"access_token": "new_at", "refresh_token": "new_rt"})
        )
        result = refresh_token(
            "https://auth.example.com/token", client_id="cid", refresh="old_rt"
        )
        assert result["access_token"] == "new_at"

    @respx.mock
    def test_includes_client_secret(self):
        route = respx.post("https://auth.example.com/token").mock(
            return_value=Response(200, json={"access_token": "at"})
        )
        refresh_token(
            "https://auth.example.com/token",
            client_id="cid",
            refresh="rt",
            client_secret="sec",
        )
        body = route.calls[0].request.content.decode()
        assert "client_secret=sec" in body


class TestBuildAuthUrl:
    def test_basic_url(self):
        url = build_auth_url(
            "https://auth.example.com/authorize",
            client_id="cid",
            redirect_uri="http://localhost:8585/callback",
            state="st",
            challenge="ch",
        )
        assert "client_id=cid" in url
        assert "state=st" in url
        assert "code_challenge=ch" in url
        assert "code_challenge_method=S256" in url

    def test_includes_scopes(self):
        url = build_auth_url(
            "https://auth.example.com/authorize",
            client_id="cid",
            redirect_uri="http://localhost:8585/callback",
            state="st",
            challenge="ch",
            scopes=["read", "write"],
        )
        assert "scope=read+write" in url

    def test_includes_extra_params(self):
        url = build_auth_url(
            "https://auth.example.com/authorize",
            client_id="cid",
            redirect_uri="http://localhost:8585/callback",
            state="st",
            challenge="ch",
            extra_params={"user_scope": "channels:read"},
        )
        assert "user_scope=channels" in url
