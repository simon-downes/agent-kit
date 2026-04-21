"""Tests for agent_kit.google.client."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from agent_kit.errors import AuthError, ConfigError
from agent_kit.google.cli import require_service
from agent_kit.google.client import GoogleClient


class TestGoogleClientInit:
    def test_valid_token(self):
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        client = GoogleClient({"access_token": "tok-123", "expires_at": future})
        assert client._token == "tok-123"

    def test_raises_when_no_token(self):
        with pytest.raises(AuthError, match="no Google credentials"):
            GoogleClient({})

    def test_refreshes_expired_token(self):
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        with patch.object(GoogleClient, "_do_refresh") as mock_refresh:
            GoogleClient({
                "access_token": "old-tok",
                "expires_at": past,
                "refresh_token": "rt",
                "client_id": "cid",
            })
            mock_refresh.assert_called_once()


class TestIsExpired:
    def test_expired_in_past(self):
        past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        assert GoogleClient._is_expired(past) is True

    def test_expires_within_60s(self):
        soon = (datetime.now(UTC) + timedelta(seconds=30)).isoformat()
        assert GoogleClient._is_expired(soon) is True

    def test_not_expired(self):
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        assert GoogleClient._is_expired(future) is False

    def test_invalid_value(self):
        assert GoogleClient._is_expired("not-a-date") is True

    def test_none_value(self):
        assert GoogleClient._is_expired(None) is True


class TestRequireService:
    def test_enabled_by_default(self):
        with patch("agent_kit.google.cli.load_config", return_value={
            "google": {"mail": {"enabled": True}},
        }):
            require_service("mail")  # should not raise

    def test_raises_when_disabled(self):
        with patch("agent_kit.google.cli.load_config", return_value={
            "google": {"mail": {"enabled": False}},
        }):
            with pytest.raises(ConfigError, match="Google mail is disabled"):
                require_service("mail")
