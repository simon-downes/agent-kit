"""Tests for agent_kit.linear.client and resolve."""

import pytest
import respx
from httpx import Response

from agent_kit.linear.client import LinearClient
from agent_kit.linear.resolve import resolve_assignee, resolve_labels, resolve_status, resolve_team_id

LINEAR_API = "https://api.linear.app/graphql/"

SAMPLE_ISSUE = {
    "id": "i1",
    "identifier": "PLAT-1",
    "title": "Fix bug",
    "state": {"name": "In Progress"},
    "assignee": {"name": "Alice"},
    "priority": 2,
    "labels": {"nodes": [{"name": "Bug"}]},
    "project": {"name": "Platform"},
    "createdAt": "2026-01-01",
    "updatedAt": "2026-01-02",
}

SAMPLE_TEAM = {
    "id": "t1",
    "name": "Platform",
    "key": "PLAT",
    "states": {"nodes": [{"id": "s1", "name": "Todo"}, {"id": "s2", "name": "Done"}]},
    "labels": {"nodes": [{"id": "l1", "name": "Bug"}, {"id": "l2", "name": "Feature"}]},
    "members": {"nodes": [{"id": "u1", "name": "Alice Smith"}, {"id": "u2", "name": "Bob"}]},
}


class TestLinearClient:
    @respx.mock
    def test_query_returns_data(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(200, json={"data": {"teams": {"nodes": []}}})
        )
        client = LinearClient("test-key")
        result = client.query("query { teams { nodes { id } } }")
        assert result == {"teams": {"nodes": []}}

    @respx.mock
    def test_graphql_error_raises(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(200, json={"errors": [{"message": "bad query"}]})
        )
        client = LinearClient("test-key")
        with pytest.raises(ValueError, match="bad query"):
            client.query("bad")

    @respx.mock
    def test_429_raises(self):
        respx.post(LINEAR_API).mock(return_value=Response(429))
        client = LinearClient("test-key")
        with pytest.raises(Exception, match="rate limit"):
            client.query("query { teams { nodes { id } } }")


class TestFormatIssue:
    def test_flattens_issue(self):
        client = LinearClient("key")
        result = client._format_issue(SAMPLE_ISSUE)
        assert result["identifier"] == "PLAT-1"
        assert result["status"] == "In Progress"
        assert result["assignee"] == "Alice"
        assert result["labels"] == ["Bug"]
        assert result["project"] == "Platform"

    def test_handles_null_assignee(self):
        client = LinearClient("key")
        issue = {**SAMPLE_ISSUE, "assignee": None}
        result = client._format_issue(issue)
        assert result["assignee"] is None


class TestGetTeams:
    @respx.mock
    def test_returns_teams(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(
                200, json={"data": {"teams": {"nodes": [{"id": "t1", "name": "Plat", "key": "PLAT"}]}}}
            )
        )
        client = LinearClient("key")
        teams = client.get_teams()
        assert len(teams) == 1
        assert teams[0]["key"] == "PLAT"


class TestGetIssues:
    @respx.mock
    def test_single_page(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(
                200,
                json={
                    "data": {
                        "issues": {
                            "nodes": [SAMPLE_ISSUE],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                },
            )
        )
        client = LinearClient("key")
        issues = client.get_issues(team_id="t1", limit=10)
        assert len(issues) == 1
        assert issues[0]["identifier"] == "PLAT-1"

    @respx.mock
    def test_pagination(self):
        respx.post(LINEAR_API).mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "data": {
                            "issues": {
                                "nodes": [SAMPLE_ISSUE],
                                "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                            }
                        }
                    },
                ),
                Response(
                    200,
                    json={
                        "data": {
                            "issues": {
                                "nodes": [{**SAMPLE_ISSUE, "id": "i2", "identifier": "PLAT-2"}],
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                            }
                        }
                    },
                ),
            ]
        )
        client = LinearClient("key")
        issues = client.get_issues(team_id="t1", limit=10)
        assert len(issues) == 2

    @respx.mock
    def test_respects_limit(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(
                200,
                json={
                    "data": {
                        "issues": {
                            "nodes": [SAMPLE_ISSUE, {**SAMPLE_ISSUE, "id": "i2"}],
                            "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                        }
                    }
                },
            )
        )
        client = LinearClient("key")
        issues = client.get_issues(team_id="t1", limit=1)
        assert len(issues) == 1


class TestGetIssue:
    @respx.mock
    def test_returns_detail(self):
        issue = {**SAMPLE_ISSUE, "description": "desc", "team": {"key": "PLAT"}, "comments": {"nodes": []}}
        respx.post(LINEAR_API).mock(
            return_value=Response(200, json={"data": {"issue": issue}})
        )
        client = LinearClient("key")
        result = client.get_issue("PLAT-1")
        assert result["description"] == "desc"
        assert result["team"] == "PLAT"

    @respx.mock
    def test_not_found(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(200, json={"data": {"issue": None}})
        )
        client = LinearClient("key")
        with pytest.raises(ValueError, match="not found"):
            client.get_issue("PLAT-999")


class TestCreateIssue:
    @respx.mock
    def test_creates(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(
                200, json={"data": {"issueCreate": {"success": True, "issue": SAMPLE_ISSUE}}}
            )
        )
        client = LinearClient("key")
        result = client.create_issue(team_id="t1", title="New")
        assert result["identifier"] == "PLAT-1"


class TestGetComments:
    @respx.mock
    def test_returns_comments(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(
                200,
                json={
                    "data": {
                        "issue": {
                            "comments": {
                                "nodes": [
                                    {"id": "c1", "body": "looks good", "createdAt": "2026-01-01", "user": {"id": "u1", "name": "Alice"}}
                                ]
                            }
                        }
                    }
                },
            )
        )
        client = LinearClient("key")
        comments = client.get_comments("PLAT-1")
        assert len(comments) == 1
        assert comments[0]["author"] == "Alice"


class TestResolve:
    @respx.mock
    def test_resolve_status(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(200, json={"data": {"team": SAMPLE_TEAM}})
        )
        client = LinearClient("key")
        assert resolve_status(client, "t1", "todo") == "s1"

    @respx.mock
    def test_resolve_status_not_found(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(200, json={"data": {"team": SAMPLE_TEAM}})
        )
        client = LinearClient("key")
        with pytest.raises(ValueError, match="Available"):
            resolve_status(client, "t1", "nonexistent")

    @respx.mock
    def test_resolve_assignee_partial(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(200, json={"data": {"team": SAMPLE_TEAM}})
        )
        client = LinearClient("key")
        assert resolve_assignee(client, "t1", "alice") == "u1"

    @respx.mock
    def test_resolve_labels(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(200, json={"data": {"team": SAMPLE_TEAM}})
        )
        client = LinearClient("key")
        assert resolve_labels(client, "t1", ["Bug", "Feature"]) == ["l1", "l2"]

    @respx.mock
    def test_resolve_labels_not_found(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(200, json={"data": {"team": SAMPLE_TEAM}})
        )
        client = LinearClient("key")
        with pytest.raises(ValueError, match="Available"):
            resolve_labels(client, "t1", ["Nonexistent"])

    @respx.mock
    def test_resolve_team_id(self):
        respx.post(LINEAR_API).mock(
            return_value=Response(200, json={"data": {"team": SAMPLE_TEAM}})
        )
        client = LinearClient("key")
        assert resolve_team_id(client, "PLAT") == "t1"
