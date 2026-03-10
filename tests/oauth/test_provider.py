"""Tests for provider configuration."""

import pytest
from agent_kit.oauth.provider import get_provider_config, load_providers


def test_load_providers():
    """Test loading provider configurations."""
    providers = load_providers()

    assert isinstance(providers, dict)
    assert "notion" in providers
    assert providers["notion"]["name"] == "Notion"
    assert providers["notion"]["server_url"] == "https://mcp.notion.com"


def test_get_provider_config():
    """Test getting specific provider config."""
    config = get_provider_config("notion")

    assert config["name"] == "Notion"
    assert config["server_url"] == "https://mcp.notion.com"


def test_get_provider_config_unknown():
    """Test getting unknown provider raises error."""
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider_config("nonexistent")
