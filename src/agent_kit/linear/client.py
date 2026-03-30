"""Linear GraphQL API client."""

import sys
from typing import Any

import httpx

API_URL = "https://api.linear.app/graphql"


class LinearClient:
    """Thin wrapper around Linear's GraphQL API."""

    def __init__(self, api_key: str):
        self._client = httpx.Client(
            base_url=API_URL,
            headers={"Authorization": api_key, "Content-Type": "application/json"},
        )

    def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query and return the data dict."""
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        resp = self._client.post("", json=payload)

        if resp.status_code == 401:
            print("Error: Linear authentication failed (invalid API key)", file=sys.stderr)
            sys.exit(2)

        body = resp.json()

        if "errors" in body:
            msgs = "; ".join(e.get("message", str(e)) for e in body["errors"])
            raise ValueError(f"GraphQL error: {msgs}")

        resp.raise_for_status()

        return body.get("data", {})

    def mutate(self, mutation: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL mutation. Same as query, just a semantic alias."""
        return self.query(mutation, variables)


# --- Queries ---

TEAMS_QUERY = """
query { teams { nodes { id name key } } }
"""

TEAM_QUERY = """
query Team($id: String!) {
  team(id: $id) {
    id name key
    states { nodes { id name type position } }
    labels { nodes { id name } }
    members { nodes { id name email } }
  }
}
"""

PROJECTS_QUERY = """
query Projects($filter: ProjectFilter) {
  projects(filter: $filter) {
    nodes { id name state }
  }
}
"""


def get_teams(client: LinearClient) -> list[dict[str, Any]]:
    data = client.query(TEAMS_QUERY)
    return data["teams"]["nodes"]


def get_team(client: LinearClient, id_or_key: str) -> dict[str, Any]:
    """Fetch team by ID or key. Tries ID first, falls back to key lookup."""
    try:
        data = client.query(TEAM_QUERY, {"id": id_or_key})
        if data.get("team"):
            return data["team"]
    except ValueError:
        pass

    # Fall back to key lookup
    teams = get_teams(client)
    for t in teams:
        if t["key"].lower() == id_or_key.lower():
            data = client.query(TEAM_QUERY, {"id": t["id"]})
            return data["team"]

    print(f"Error: team '{id_or_key}' not found", file=sys.stderr)
    sys.exit(1)


def get_projects(client: LinearClient, *, team_key: str | None = None) -> list[dict[str, Any]]:
    filt: dict[str, Any] | None = None
    if team_key:
        team = get_team(client, team_key)
        filt = {"accessibleTeams": {"id": {"eq": team["id"]}}}
    data = client.query(PROJECTS_QUERY, {"filter": filt})
    return data["projects"]["nodes"]


# --- Issue queries ---

ISSUES_QUERY = """
query Issues($filter: IssueFilter, $first: Int) {
  issues(filter: $filter, first: $first) {
    nodes {
      id identifier title priority
      state { id name type }
      assignee { id name }
      labels { nodes { id name } }
      project { id name }
      createdAt updatedAt
    }
  }
}
"""

ISSUE_QUERY = """
query Issue($id: String!) {
  issue(id: $id) {
    id identifier title description priority
    state { id name type }
    assignee { id name }
    labels { nodes { id name } }
    project { id name }
    team { id name key }
    createdAt updatedAt
    comments { nodes { id body createdAt user { id name } } }
  }
}
"""


def _format_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Flatten an issue into a clean output dict."""
    return {
        "id": issue["id"],
        "identifier": issue["identifier"],
        "title": issue["title"],
        "status": issue.get("state", {}).get("name"),
        "assignee": (issue.get("assignee") or {}).get("name"),
        "priority": issue.get("priority"),
        "labels": [lbl["name"] for lbl in issue.get("labels", {}).get("nodes", [])],
        "project": (issue.get("project") or {}).get("name"),
        "createdAt": issue.get("createdAt"),
        "updatedAt": issue.get("updatedAt"),
    }


def _format_issue_detail(issue: dict[str, Any]) -> dict[str, Any]:
    """Flatten an issue with full detail."""
    result = _format_issue(issue)
    result["description"] = issue.get("description")
    result["team"] = issue.get("team", {}).get("key")
    result["comments"] = [
        {
            "author": c.get("user", {}).get("name"),
            "body": c.get("body"),
            "createdAt": c.get("createdAt"),
        }
        for c in issue.get("comments", {}).get("nodes", [])
    ]
    return result


def get_issues(
    client: LinearClient,
    *,
    team_id: str,
    status_id: str | None = None,
    assignee_id: str | None = None,
    label_id: str | None = None,
    project_name: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List issues with server-side filtering."""
    filt: dict[str, Any] = {"team": {"id": {"eq": team_id}}}
    if status_id:
        filt["state"] = {"id": {"eq": status_id}}
    if assignee_id:
        filt["assignee"] = {"id": {"eq": assignee_id}}
    if label_id:
        filt["labels"] = {"id": {"eq": label_id}}
    if project_name:
        filt["project"] = {"name": {"eqIgnoreCase": project_name}}

    data = client.query(ISSUES_QUERY, {"filter": filt, "first": limit})
    return [_format_issue(i) for i in data["issues"]["nodes"]]


def get_issue(client: LinearClient, identifier: str) -> dict[str, Any]:
    """Fetch a single issue by identifier (e.g. PLAT-123) or UUID."""
    data = client.query(ISSUE_QUERY, {"id": identifier})
    issue = data.get("issue")
    if not issue:
        print(f"Error: issue '{identifier}' not found", file=sys.stderr)
        sys.exit(1)
    return _format_issue_detail(issue)


# --- Mutations ---

ISSUE_CREATE = """
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue { id identifier title state { name } assignee { name } priority }
  }
}
"""

ISSUE_UPDATE = """
mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(id: $id, input: $input) {
    success
    issue { id identifier title state { name } assignee { name } priority }
  }
}
"""

COMMENT_CREATE = """
mutation CommentCreate($input: CommentCreateInput!) {
  commentCreate(input: $input) {
    success
    comment { id body createdAt user { name } }
  }
}
"""

COMMENTS_QUERY = """
query IssueComments($id: String!) {
  issue(id: $id) {
    comments { nodes { id body createdAt user { id name } } }
  }
}
"""

FILE_UPLOAD = """
mutation FileUpload($contentType: String!, $filename: String!, $size: Int!) {
  fileUpload(contentType: $contentType, filename: $filename, size: $size) {
    success
    uploadFile { uploadUrl assetUrl headers { key value } }
  }
}
"""


def create_issue(
    client: LinearClient,
    *,
    team_id: str,
    title: str,
    description: str | None = None,
    state_id: str | None = None,
    assignee_id: str | None = None,
    priority: int | None = None,
    label_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create an issue."""
    inp: dict[str, Any] = {"teamId": team_id, "title": title}
    if description:
        inp["description"] = description
    if state_id:
        inp["stateId"] = state_id
    if assignee_id:
        inp["assigneeId"] = assignee_id
    if priority is not None:
        inp["priority"] = priority
    if label_ids:
        inp["labelIds"] = label_ids

    data = client.mutate(ISSUE_CREATE, {"input": inp})
    return _format_issue(data["issueCreate"]["issue"])


def update_issue(
    client: LinearClient,
    identifier: str,
    *,
    title: str | None = None,
    state_id: str | None = None,
    assignee_id: str | None = None,
    priority: int | None = None,
    label_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Update an issue."""
    inp: dict[str, Any] = {}
    if title:
        inp["title"] = title
    if state_id:
        inp["stateId"] = state_id
    if assignee_id:
        inp["assigneeId"] = assignee_id
    if priority is not None:
        inp["priority"] = priority
    if label_ids is not None:
        inp["labelIds"] = label_ids

    data = client.mutate(ISSUE_UPDATE, {"id": identifier, "input": inp})
    return _format_issue(data["issueUpdate"]["issue"])


def get_comments(client: LinearClient, identifier: str) -> list[dict[str, Any]]:
    """Fetch comments on an issue."""
    data = client.query(COMMENTS_QUERY, {"id": identifier})
    issue = data.get("issue")
    if not issue:
        print(f"Error: issue '{identifier}' not found", file=sys.stderr)
        sys.exit(1)
    return [
        {
            "author": c.get("user", {}).get("name"),
            "body": c.get("body"),
            "createdAt": c.get("createdAt"),
        }
        for c in issue.get("comments", {}).get("nodes", [])
    ]


def create_comment(client: LinearClient, identifier: str, *, body: str) -> dict[str, Any]:
    """Add a comment to an issue."""
    data = client.mutate(COMMENT_CREATE, {"input": {"issueId": identifier, "body": body}})
    c = data["commentCreate"]["comment"]
    return {
        "id": c["id"],
        "author": c.get("user", {}).get("name"),
        "body": c["body"],
        "createdAt": c["createdAt"],
    }


def upload_file(client: LinearClient, filepath: str) -> dict[str, Any]:
    """Upload a file to Linear's storage. Returns asset URL."""
    import mimetypes
    from pathlib import Path

    path = Path(filepath)
    if not path.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    size = path.stat().st_size

    data = client.mutate(
        FILE_UPLOAD,
        {"contentType": content_type, "filename": path.name, "size": size},
    )
    upload = data["fileUpload"]["uploadFile"]

    headers = {"Content-Type": content_type, "Cache-Control": "public, max-age=31536000"}
    for h in upload["headers"]:
        headers[h["key"]] = h["value"]

    resp = httpx.put(upload["uploadUrl"], content=path.read_bytes(), headers=headers)
    resp.raise_for_status()

    return {"assetUrl": upload["assetUrl"], "filename": path.name}
