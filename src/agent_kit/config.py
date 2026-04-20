"""Configuration loading and validation."""

import sys
from pathlib import Path

import yaml

CONFIG_PATH = Path("~/.agent-kit/config.yaml").expanduser()

DEFAULT_CONFIG = {
    "project_dir": "~/dev",
    "brain": {
        "dir": "~/.archie/brain",
        "contexts": {},
    },
    "auth": {
        "notion": {"type": "oauth"},
        "linear": {"type": "static", "fields": ["token"]},
        "slack": {"type": "static", "fields": ["webhook_url"]},
        "github": {"type": "static", "fields": ["token"]},
        "aws": {
            "type": "static",
            "fields": ["access_key_id", "secret_access_key", "session_token"],
        },
        "scalr": {"type": "static", "fields": ["token", "hostname"]},
        "jira": {"type": "static", "fields": ["email", "token", "cloud_id"]},
        "google": {
            "type": "oauth",
            "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_endpoint": "https://oauth2.googleapis.com/token",
            "scopes": [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/calendar.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/userinfo.email",
            ],
            "extra_params": {"access_type": "offline", "prompt": "consent"},
        },
    },
    "notion": {
        "read": {"enabled": True, "scope": {"pages": [], "databases": []}},
        "write": {"enabled": False, "scope": {"pages": [], "databases": []}},
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config() -> dict:
    """Load config from YAML file, deep-merged with defaults."""
    if not CONFIG_PATH.exists():
        return dict(DEFAULT_CONFIG)

    try:
        raw = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    except Exception as e:
        print(f"Error reading config {CONFIG_PATH}: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(raw, dict):
        print(
            f"Error: config file must be a YAML mapping, got {type(raw).__name__}",
            file=sys.stderr,
        )
        sys.exit(1)

    return _deep_merge(DEFAULT_CONFIG, raw)


def save_config(data: dict) -> None:
    """Write config to YAML file."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
