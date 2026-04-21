"""Shared fixtures for agent-kit tests."""

from unittest.mock import patch

import click.testing
import pytest

from agent_kit.config import DEFAULT_CONFIG, _deep_merge


@pytest.fixture
def cli_runner():
    """Click CLI test runner."""
    return click.testing.CliRunner()


@pytest.fixture
def mock_config():
    """Factory fixture that patches load_config() to return a config with optional overrides."""

    def _factory(overrides=None):
        config = _deep_merge(DEFAULT_CONFIG, overrides or {})
        patcher = patch("agent_kit.config.load_config", return_value=config)
        patcher.start()
        return config

    yield _factory
    # patch.stopall handles cleanup even if _factory was never called
    patch.stopall()


@pytest.fixture
def mock_credentials():
    """Patches get_field/set_field against an in-memory dict."""
    store: dict[str, dict[str, str]] = {}

    def _get_field(service, field):
        return store.get(service, {}).get(field)

    def _set_field(service, field, value):
        store.setdefault(service, {})[field] = value

    with (
        patch("agent_kit.auth.get_field", side_effect=_get_field),
        patch("agent_kit.auth.set_field", side_effect=_set_field),
    ):
        yield store


@pytest.fixture
def cache_dir(tmp_path):
    """Provides a temp cache directory and patches Slack's _get_cache_dir."""
    d = tmp_path / "cache"
    d.mkdir()
    with patch("agent_kit.slack.resolve._get_cache_dir", return_value=d):
        yield d


@pytest.fixture(autouse=True)
def _reset_module_globals():
    """Reset module-level caches between tests."""
    yield
    # Slack
    import agent_kit.slack.api as slack_api
    import agent_kit.slack.resolve as slack_resolve

    slack_api._cached_token = None
    slack_resolve._cache_dir = None
    slack_resolve._user_cache = None
    slack_resolve._channel_cache = None
    slack_resolve._dm_cache = None

    # Google
    try:
        import agent_kit.google.auth as google_auth

        google_auth._cached_token = None
    except ImportError:
        pass
