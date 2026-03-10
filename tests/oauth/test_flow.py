"""Tests for OAuth flow functions."""

from agent_kit.oauth.flow import base64url_encode, build_authorization_url, generate_pkce


def test_base64url_encode():
    """Test base64url encoding."""
    data = b"test data"
    encoded = base64url_encode(data)
    assert isinstance(encoded, str)
    assert "=" not in encoded  # No padding
    assert "+" not in encoded  # URL-safe
    assert "/" not in encoded  # URL-safe


def test_generate_pkce():
    """Test PKCE generation."""
    verifier, challenge = generate_pkce()

    assert isinstance(verifier, str)
    assert isinstance(challenge, str)
    assert len(verifier) > 0
    assert len(challenge) > 0
    assert verifier != challenge

    # Generate again to ensure randomness
    verifier2, challenge2 = generate_pkce()
    assert verifier != verifier2
    assert challenge != challenge2


def test_build_authorization_url():
    """Test authorization URL building."""
    url = build_authorization_url(
        authorization_endpoint="https://example.com/auth",
        client_id="test-client",
        redirect_uri="http://localhost:3000/callback",
        state="test-state",
        challenge="test-challenge",
    )

    assert url.startswith("https://example.com/auth?")
    assert "response_type=code" in url
    assert "client_id=test-client" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fcallback" in url
    assert "state=test-state" in url
    assert "code_challenge=test-challenge" in url
    assert "code_challenge_method=S256" in url


def test_build_authorization_url_with_extra_params():
    """Test authorization URL with extra parameters."""
    url = build_authorization_url(
        authorization_endpoint="https://example.com/auth",
        client_id="test-client",
        redirect_uri="http://localhost:3000/callback",
        state="test-state",
        challenge="test-challenge",
        extra_params={"prompt": "consent", "scope": "read write"},
    )

    assert "prompt=consent" in url
    assert "scope=read+write" in url
