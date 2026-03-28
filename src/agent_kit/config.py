"""Configuration loading and validation."""

import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_PATH = Path("~/.agent-kit/config.yaml").expanduser()

DEFAULT_CONFIG = {
    "notion": {
        "operations": {"read": True, "write": False},
        "scope": {"pages": [], "databases": []},
    },
}


@dataclass
class ScopeConfig:
    pages: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)


@dataclass
class OperationsConfig:
    read: bool = True
    write: bool = False


@dataclass
class NotionConfig:
    operations: OperationsConfig = field(default_factory=OperationsConfig)
    scope: ScopeConfig = field(default_factory=ScopeConfig)


@dataclass
class Config:
    notion: NotionConfig = field(default_factory=NotionConfig)


def _build_config(data: dict) -> Config:
    """Build a Config from a raw dict, merging with defaults."""
    merged = DEFAULT_CONFIG.copy()
    if "notion" in data and isinstance(data["notion"], dict):
        for key in ("operations", "scope"):
            if key in data["notion"] and isinstance(data["notion"][key], dict):
                merged["notion"][key] = {**merged["notion"][key], **data["notion"][key]}

    n = merged["notion"]
    return Config(
        notion=NotionConfig(
            operations=OperationsConfig(**n["operations"]),
            scope=ScopeConfig(**n["scope"]),
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
