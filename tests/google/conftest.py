"""Shared fixtures for Google tests."""

from unittest.mock import patch

import pytest

from agent_kit.google.client import GoogleClient


@pytest.fixture()
def google_client():
    """Create a GoogleClient that skips auth entirely."""
    creds = {"access_token": "fake-tok", "expires_at": "2099-01-01T00:00:00+00:00"}
    return GoogleClient(creds)


@pytest.fixture(autouse=True)
def _patch_get_client(google_client):
    """Patch _get_client in cli.py so CLI tests use the fake client."""
    with patch("agent_kit.google.cli._get_client", return_value=google_client):
        yield
