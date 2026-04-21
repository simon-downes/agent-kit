"""Shared fixtures for Google tests."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _fake_google_token():
    """Patch get_token at all usage sites so API calls never hit real auth."""
    with (
        patch("agent_kit.google.mail.get_token", return_value="fake-tok"),
        patch("agent_kit.google.calendar.get_token", return_value="fake-tok"),
        patch("agent_kit.google.drive.get_token", return_value="fake-tok"),
    ):
        yield
