"""Credential store — read/write ~/.agent-kit/credentials.yaml with 0600 permissions."""

import os
import stat
import sys
from pathlib import Path

import yaml

AGENT_KIT_HOME = Path.home() / ".agent-kit"
CREDENTIALS_PATH = AGENT_KIT_HOME / "credentials.yaml"


def load_credentials() -> dict:
    """Load credentials file. Warn if permissions too permissive."""
    if not CREDENTIALS_PATH.exists():
        return {}

    mode = stat.S_IMODE(CREDENTIALS_PATH.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        print(
            f"Warning: {CREDENTIALS_PATH} has permissions {oct(mode)} — expected 0600",
            file=sys.stderr,
        )

    try:
        with CREDENTIALS_PATH.open() as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"invalid YAML in {CREDENTIALS_PATH}: {e}") from e


def save_credentials(data: dict) -> None:
    """Write credentials file with 0600 permissions."""
    AGENT_KIT_HOME.mkdir(parents=True, exist_ok=True)
    if not CREDENTIALS_PATH.exists():
        fd = os.open(str(CREDENTIALS_PATH), os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)

    CREDENTIALS_PATH.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    os.chmod(str(CREDENTIALS_PATH), 0o600)


def get_field(service: str, field: str) -> str | None:
    """Get a credential field. Returns None if not found."""
    creds = load_credentials()
    service_data = creds.get(service)
    if isinstance(service_data, dict):
        value = service_data.get(field)
        return str(value) if value is not None else None
    return None


def set_field(service: str, field: str, value: str) -> None:
    """Set a credential field."""
    creds = load_credentials()
    if service not in creds:
        creds[service] = {}
    creds[service][field] = value
    save_credentials(creds)


def set_fields(service: str, fields: dict[str, str]) -> None:
    """Set multiple credential fields in one write."""
    creds = load_credentials()
    if service not in creds:
        creds[service] = {}
    creds[service].update(fields)
    save_credentials(creds)
