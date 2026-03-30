"""Configuration loading and validation."""

import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_PATH = Path("~/.agent-kit/config.yaml").expanduser()

DEFAULT_CONFIG = {
    "notion": {
        "read": {"enabled": True, "scope": {"pages": [], "databases": []}},
        "write": {"enabled": False, "scope": {"pages": [], "databases": []}},
    },
}


@dataclass
class ScopeConfig:
    pages: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)


@dataclass
class AccessConfig:
    enabled: bool = True
    scope: ScopeConfig = field(default_factory=ScopeConfig)


@dataclass
class NotionConfig:
    read: AccessConfig = field(default_factory=AccessConfig)
    write: AccessConfig = field(default_factory=lambda: AccessConfig(enabled=False))


@dataclass
class Config:
    notion: NotionConfig = field(default_factory=NotionConfig)


def _build_access(data: dict, defaults: dict) -> AccessConfig:
    """Build an AccessConfig from raw dict merged with defaults."""
    merged = {**defaults, **data}
    scope_data = {**defaults.get("scope", {}), **data.get("scope", {})}
    return AccessConfig(
        enabled=merged.get("enabled", defaults["enabled"]),
        scope=ScopeConfig(**scope_data),
    )


def _build_config(data: dict) -> Config:
    """Build a Config from a raw dict, merging with defaults."""
    nd = data.get("notion", {}) if isinstance(data.get("notion"), dict) else {}
    defaults = DEFAULT_CONFIG["notion"]

    read_data = nd.get("read", {}) if isinstance(nd.get("read"), dict) else {}
    write_data = nd.get("write", {}) if isinstance(nd.get("write"), dict) else {}

    return Config(
        notion=NotionConfig(
            read=_build_access(read_data, defaults["read"]),
            write=_build_access(write_data, defaults["write"]),
        )
    )


def load_config() -> Config:
    """Load config from YAML file, falling back to defaults."""
    if not CONFIG_PATH.exists():
        return _build_config({})

    try:
        raw = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    except Exception as e:
        print(f"Error reading config {CONFIG_PATH}: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(raw, dict):
        msg = f"Error: config file must be a YAML mapping, got {type(raw).__name__}"
        print(msg, file=sys.stderr)
        sys.exit(1)

    return _build_config(raw)
