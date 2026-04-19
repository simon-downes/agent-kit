"""Name → ID resolution for Jira entities."""

from agent_kit.jira.client import JiraClient, get_transitions, search_users


def resolve_assignee(client: JiraClient, name: str) -> str:
    """Resolve an assignee name to an account ID. Case-insensitive partial match."""
    users = search_users(client, name)
    if not users:
        raise ValueError(f"Assignee '{name}' not found")
    name_lower = name.lower()
    for u in users:
        if name_lower in u["displayName"].lower():
            return u["accountId"]
    # Fall back to first result if no partial match
    return users[0]["accountId"]


def resolve_transition(client: JiraClient, key: str, status_name: str) -> str:
    """Resolve a status name to a transition ID. Case-insensitive."""
    transitions = get_transitions(client, key)
    name_lower = status_name.lower()
    for t in transitions:
        if t["name"].lower() == name_lower:
            return t["id"]
    available = [t["name"] for t in transitions]
    raise ValueError(f"Transition '{status_name}' not available. Available: {', '.join(available)}")
