"""Tests for agent_kit.google.auth."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from agent_kit.errors import AuthError, ConfigError
from agent_kit.google.auth import _is_expired, get_token, require_service


@pytest.fixture(autouse=True)
def _reset_cache():
    import agent_kit.google.auth as mod

    mod._cached_token = None
    yield
    mod._cached_token = None


class TestGetToken:
    def test_returns_cached_token(self):
        import agent_kit.google.auth as mod

        mod._cached_token = "cached-tok"
        assert get_token() == "cached-tok"

    def test_returns_valid_token(self):
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        with patch("agent_kit.google.auth.get_field", side_effect=lambda s, f: {
            "access_token": "tok-123",
            "expires_at": future,
        }.get(f)):
            assert get_token() == "tok-123"

    def test_raises_when_no_token(self):
        with patch("agent_kit.google.auth.get_field", return_value=None):
            with pytest.raises(AuthError, match="no Google credentials"):
                get_token()

    def test_refreshes_expired_token(self):
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        with (
            patch("agent_kit.google.auth.get_field", side_effect=lambda s, f: {
                "access_token": "old-tok",
                "expires_at": past,
            }.get(f)),
            patch("agent_kit.google.auth._refresh", return_value="new-tok") as mock_refresh,
        ):
            assert get_token() == "new-tok"
            mock_refresh.assert_called_once()


class TestIsExpired:
    def test_expired_in_past(self):
        past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        assert _is_expired(past) is True

    def test_expires_within_60s(self):
        soon = (datetime.now(UTC) + timedelta(seconds=30)).isoformat()
        assert _is_expired(soon) is True

    def test_not_expired(self):
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        assert _is_expired(future) is False

    def test_invalid_value(self):
        assert _is_expired("not-a-date") is True

    def test_none_value(self):
        assert _is_expired(None) is True


class TestRequireService:
    def test_enabled_by_default(self):
        with patch("agent_kit.google.auth.load_config", return_value={
            "google": {"mail": {"enabled": True}},
        }):
            require_service("mail")  # should not raise

    def test_raises_when_disabled(self):
        with patch("agent_kit.google.auth.load_config", return_value={
            "google": {"mail": {"enabled": False}},
        }):
            with pytest.raises(ConfigError, match="Google mail is disabled"):
                require_service("mail")
