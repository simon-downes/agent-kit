"""Name → ID resolution for Linear entities."""

from agent_kit.linear.client import LinearClient


def resolve_status(client: LinearClient, team_id_or_key: str, name: str) -> str:
    """Resolve a status name to a workflow state ID. Case-insensitive."""
    team = client.get_team(team_id_or_key)
    name_lower = name.lower()
    for state in team["states"]["nodes"]:
        if state["name"].lower() == name_lower:
            return state["id"]
    available = [s["name"] for s in team["states"]["nodes"]]
    raise ValueError(f"Status '{name}' not found. Available: {', '.join(available)}")


def resolve_assignee(client: LinearClient, team_id_or_key: str, name: str) -> str:
    """Resolve an assignee name to a user ID. Case-insensitive partial match."""
    team = client.get_team(team_id_or_key)
    name_lower = name.lower()
    for member in team["members"]["nodes"]:
        if name_lower in member["name"].lower():
            return member["id"]
    available = [m["name"] for m in team["members"]["nodes"]]
    raise ValueError(f"Assignee '{name}' not found. Available: {', '.join(available)}")


def resolve_labels(client: LinearClient, team_id_or_key: str, names: list[str]) -> list[str]:
    """Resolve label names to IDs. Case-insensitive."""
    team = client.get_team(team_id_or_key)
    label_map = {lbl["name"].lower(): lbl["id"] for lbl in team["labels"]["nodes"]}
    ids = []
    for name in names:
        lid = label_map.get(name.lower())
        if not lid:
            available = [lbl["name"] for lbl in team["labels"]["nodes"]]
            raise ValueError(f"Label '{name}' not found. Available: {', '.join(available)}")
        ids.append(lid)
    return ids


def resolve_team_id(client: LinearClient, team_key: str) -> str:
    """Resolve a team key to its ID."""
    team = client.get_team(team_key)
    return team["id"]
