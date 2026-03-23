"""OAuth token retrieval."""

import json
from typing import Any

from agent_kit.kv import db


def get_token(provider: str) -> dict[str, Any] | None:
    """Get stored OAuth token data for a provider.

    Returns dict with access_token and other token data, or None if not authenticated.
    """
    token_json = db.get(f"oauth-{provider}")
    if not token_json:
        return None
    return json.loads(token_json)
