"""Provider configuration management."""

from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path.home() / ".cli-tools" / "oauth"
CONFIG_FILE = CONFIG_DIR / "providers.yaml"


def ensure_config() -> None:
    """Ensure config directory and file exist."""
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Copy default config from package
        default_config = files("oauth").joinpath("providers.yaml")
        CONFIG_FILE.write_text(default_config.read_text())


def load_providers() -> dict[str, Any]:
    """Load provider configurations."""
    ensure_config()

    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)

    return config.get("providers", {})  # type: ignore[no-any-return]


def get_provider_config(provider: str) -> dict[str, Any]:
    """Get configuration for a specific provider."""
    providers = load_providers()

    if provider not in providers:
        raise ValueError(f"Unknown provider: {provider}")

    return providers[provider]  # type: ignore[no-any-return]


def get_provider_endpoints(config: dict[str, Any]) -> dict[str, str]:
    """Get OAuth endpoints from provider config.

    If explicit endpoints are provided, use those.
    Otherwise, perform dynamic discovery using server_url.
    """
    from oauth.flow import discover_oauth_metadata

    # Check for explicit endpoints
    if "authorization_endpoint" in config and "token_endpoint" in config:
        return {
            "authorization_endpoint": config["authorization_endpoint"],
            "token_endpoint": config["token_endpoint"],
            "registration_endpoint": config.get("registration_endpoint"),
            "revocation_endpoint": config.get("revocation_endpoint"),
        }

    # Dynamic discovery
    if "server_url" not in config:
        raise ValueError("Provider config must have either explicit endpoints or server_url")

    metadata = discover_oauth_metadata(config["server_url"])

    return {
        "authorization_endpoint": metadata["authorization_endpoint"],
        "token_endpoint": metadata["token_endpoint"],
        "registration_endpoint": metadata.get("registration_endpoint"),
        "revocation_endpoint": metadata.get("revocation_endpoint"),
    }
