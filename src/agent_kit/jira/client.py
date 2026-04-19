"""Jira Cloud REST API v3 client."""

from typing import Any

import httpx


class JiraClient:
    """Thin wrapper around Jira Cloud REST API v3 using scoped API tokens."""

    def __init__(self, email: str, token: str, cloud_id: str):
        self._client = httpx.Client(
            base_url=f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3",
            auth=(email, token),
            headers={"Accept": "application/json"},
        )

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._client.get(path, params=params)
        return self._handle(resp)

    def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        resp = self._client.post(path, json=json)
        return self._handle(resp)

    def put(self, path: str, json: dict[str, Any] | None = None) -> Any:
        resp = self._client.put(path, json=json)
        return self._handle(resp)

    def post_raw(self, path: str, **kwargs: Any) -> httpx.Response:
        """POST without JSON encoding — for multipart uploads."""
        resp = self._client.post(path, **kwargs)
        return self._handle_response(resp)

    def _handle(self, resp: httpx.Response) -> Any:
        resp = self._handle_response(resp)
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def _handle_response(self, resp: httpx.Response) -> httpx.Response:
        if resp.status_code in (401, 403):
            resp.raise_for_status()

        if resp.status_code == 429:
            raise httpx.HTTPStatusError(
                "Jira API rate limit exceeded, try again later",
                request=resp.request,
                response=resp,
            )

        if resp.status_code >= 400:
            self._raise_api_error(resp)

        return resp

    def _raise_api_error(self, resp: httpx.Response) -> None:
        try:
            body = resp.json()
        except Exception:
            resp.raise_for_status()

        parts: list[str] = []
        for msg in body.get("errorMessages", []):
            if msg:
                parts.append(msg)
        for field, msg in body.get("errors", {}).items():
            parts.append(f"{field}: {msg}")

        if parts:
            raise ValueError("; ".join(parts))
        resp.raise_for_status()


# --- ADF helpers ---


def adf_to_text(doc: dict[str, Any] | None) -> str:
    """Extract plain text from an Atlassian Document Format document."""
    if not doc or not isinstance(doc, dict):
        return ""
    return _extract_blocks(doc.get("content", [])).strip()


def _extract_blocks(nodes: list[dict[str, Any]], depth: int = 0) -> str:
    parts: list[str] = []
    for node in nodes:
        ntype = node.get("type", "")
        content = node.get("content", [])

        if ntype == "paragraph":
            parts.append(_extract_inline(content))
        elif ntype == "heading":
            level = node.get("attrs", {}).get("level", 1)
            parts.append("#" * level + " " + _extract_inline(content))
        elif ntype in ("bulletList", "orderedList"):
            for i, item in enumerate(content):
                prefix = "- " if ntype == "bulletList" else f"{i + 1}. "
                item_text = _extract_inline(item.get("content", [{}])[0].get("content", []))
                parts.append(prefix + item_text)
        elif ntype == "codeBlock":
            parts.append("```\n" + _extract_inline(content) + "\n```")
        elif ntype == "blockquote":
            inner = _extract_blocks(content, depth + 1)
            parts.append("\n".join("> " + line for line in inner.splitlines()))
        elif content:
            parts.append(_extract_blocks(content, depth + 1))

    return "\n\n".join(str(p) for p in parts if p)


def _extract_inline(nodes: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for node in nodes:
        if node.get("type") == "text":
            parts.append(node.get("text", ""))
        elif node.get("type") == "hardBreak":
            parts.append("\n")
        elif "content" in node:
            parts.append(_extract_inline(node["content"]))
    return "".join(parts)


def text_to_adf(text: str) -> dict[str, Any]:
    """Convert plain text to minimal ADF document."""
    paragraphs = []
    for line in text.split("\n"):
        if line.strip():
            paragraphs.append(
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": line}],
                }
            )
    if not paragraphs:
        paragraphs.append({"type": "paragraph", "content": []})
    return {"type": "doc", "version": 1, "content": paragraphs}


# --- Project queries ---


def get_projects(client: JiraClient, *, limit: int = 50) -> list[dict[str, Any]]:
    data = client.get("/project/search", params={"maxResults": limit})
    return [
        {
            "id": p["id"],
            "key": p["key"],
            "name": p["name"],
            "projectTypeKey": p.get("projectTypeKey"),
        }
        for p in data.get("values", [])
    ]


def get_project(client: JiraClient, key_or_id: str) -> dict[str, Any]:
    data = client.get(f"/project/{key_or_id}", params={"expand": "issueTypes"})
    return {
        "id": data["id"],
        "key": data["key"],
        "name": data["name"],
        "projectTypeKey": data.get("projectTypeKey"),
        "issueTypes": [
            {"id": t["id"], "name": t["name"], "subtask": t.get("subtask", False)}
            for t in data.get("issueTypes", [])
        ],
    }


def get_statuses(client: JiraClient, project_key: str) -> list[dict[str, Any]]:
    data = client.get(f"/project/{project_key}/statuses")
    return [
        {
            "issueType": entry["name"],
            "statuses": [{"id": s["id"], "name": s["name"]} for s in entry.get("statuses", [])],
        }
        for entry in data
    ]


# --- Issue queries ---


def search_issues(
    client: JiraClient,
    *,
    jql: str | None = None,
    project: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
    issue_type: str | None = None,
    label: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if jql is None:
        clauses: list[str] = []
        if project:
            clauses.append(f'project = "{project}"')
        if status:
            clauses.append(f'status = "{status}"')
        if assignee:
            clauses.append(f'assignee = "{assignee}"')
        if issue_type:
            clauses.append(f'issuetype = "{issue_type}"')
        if label:
            clauses.append(f'labels = "{label}"')
        jql = " AND ".join(clauses) if clauses else "ORDER BY created DESC"

    fields = "summary,status,assignee,priority,issuetype,labels,created,updated"
    data = client.post(
        "/search/jql",
        json={"jql": jql, "maxResults": limit, "fields": fields.split(",")},
    )
    return [_format_issue(i) for i in data.get("issues", [])]


def get_issue(client: JiraClient, key: str) -> dict[str, Any]:
    data = client.get(f"/issue/{key}")
    return _format_issue_detail(data)


def _format_issue(issue: dict[str, Any]) -> dict[str, Any]:
    fields = issue.get("fields", {})
    return {
        "key": issue["key"],
        "summary": fields.get("summary"),
        "status": (fields.get("status") or {}).get("name"),
        "assignee": (fields.get("assignee") or {}).get("displayName"),
        "priority": (fields.get("priority") or {}).get("name"),
        "issuetype": (fields.get("issuetype") or {}).get("name"),
        "labels": fields.get("labels", []),
        "created": fields.get("created"),
        "updated": fields.get("updated"),
    }


def _format_issue_detail(issue: dict[str, Any]) -> dict[str, Any]:
    result = _format_issue(issue)
    fields = issue.get("fields", {})
    result["description"] = adf_to_text(fields.get("description"))
    result["project"] = (fields.get("project") or {}).get("key")
    comments = fields.get("comment", {}).get("comments", [])
    result["comments"] = [
        {
            "author": (c.get("author") or {}).get("displayName"),
            "body": adf_to_text(c.get("body")),
            "created": c.get("created"),
        }
        for c in comments
    ]
    return result


# --- Issue mutations ---


def create_issue(
    client: JiraClient,
    *,
    project_key: str,
    summary: str,
    issue_type: str,
    description: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    assignee_id: str | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
    }
    if description:
        fields["description"] = text_to_adf(description)
    if priority:
        fields["priority"] = {"name": priority}
    if labels:
        fields["labels"] = labels
    if assignee_id:
        fields["assignee"] = {"accountId": assignee_id}

    data = client.post("/issue", json={"fields": fields})
    return {"key": data["key"], "id": data["id"], "self": data.get("self")}


def update_issue(
    client: JiraClient,
    key: str,
    *,
    summary: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    assignee_id: str | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if summary:
        fields["summary"] = summary
    if description:
        fields["description"] = text_to_adf(description)
    if priority:
        fields["priority"] = {"name": priority}
    if labels is not None:
        fields["labels"] = labels
    if assignee_id:
        fields["assignee"] = {"accountId": assignee_id}

    client.put(f"/issue/{key}", json={"fields": fields})
    return get_issue(client, key)


def get_transitions(client: JiraClient, key: str) -> list[dict[str, Any]]:
    data = client.get(f"/issue/{key}/transitions")
    return [{"id": t["id"], "name": t["name"]} for t in data.get("transitions", [])]


def transition_issue(client: JiraClient, key: str, *, transition_id: str) -> dict[str, Any]:
    client.post(f"/issue/{key}/transitions", json={"transition": {"id": transition_id}})
    return get_issue(client, key)


# --- Comments ---


def get_comments(client: JiraClient, key: str) -> list[dict[str, Any]]:
    data = client.get(f"/issue/{key}/comment")
    return [
        {
            "id": c["id"],
            "author": (c.get("author") or {}).get("displayName"),
            "body": adf_to_text(c.get("body")),
            "created": c.get("created"),
        }
        for c in data.get("comments", [])
    ]


def create_comment(client: JiraClient, key: str, *, body: str) -> dict[str, Any]:
    data = client.post(f"/issue/{key}/comment", json={"body": text_to_adf(body)})
    return {
        "id": data["id"],
        "author": (data.get("author") or {}).get("displayName"),
        "body": adf_to_text(data.get("body")),
        "created": data.get("created"),
    }


# --- Attachments ---


def attach_file(client: JiraClient, key: str, filepath: str) -> list[dict[str, Any]]:
    """Attach a file to an issue. Returns list of created attachments."""
    from pathlib import Path

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {filepath}")

    with path.open("rb") as f:
        resp = client.post_raw(
            f"/issue/{key}/attachments",
            files={"file": (path.name, f)},
            headers={"X-Atlassian-Token": "no-check"},
        )

    attachments = resp.json()
    return [
        {
            "id": a["id"],
            "filename": a["filename"],
            "size": a.get("size"),
            "content": a.get("content"),
        }
        for a in attachments
    ]


# --- User search ---


def search_users(client: JiraClient, query: str) -> list[dict[str, Any]]:
    data = client.get("/user/search", params={"query": query, "maxResults": 10})
    return [
        {"accountId": u["accountId"], "displayName": u.get("displayName", "")}
        for u in data
        if u.get("accountType") == "atlassian"
    ]
