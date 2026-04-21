"""Tests for agent_kit.linear.cli."""

import json
from unittest.mock import patch

import pytest
import respx
from httpx import Response

from agent_kit.linear.cli import linear

LINEAR_API = "https://api.linear.app/graphql/"

TEAMS_DATA = {"data": {"teams": {"nodes": [{"id": "t1", "name": "Platform", "key": "PLAT"}]}}}

TEAM_DATA = {
    "data": {
        "team": {
            "id": "t1",
            "name": "Platform",
            "key": "PLAT",
            "states": {"nodes": [{"id": "s1", "name": "Todo", "type": "unstarted", "color": "#ccc"}]},
            "labels": {"nodes": [{"id": "l1", "name": "Bug"}]},
            "members": {"nodes": [{"id": "u1", "name": "Alice", "email": "a@co.com"}]},
        }
    }
}

ISSUE_NODE = {
    "id": "i1",
    "identifier": "PLAT-1",
    "title": "Fix bug",
    "state": {"name": "Todo"},
    "assignee": {"name": "Alice"},
    "priority": 2,
    "labels": {"nodes": [{"name": "Bug"}]},
    "project": {"name": "Core"},
    "createdAt": "2026-01-01",
    "updatedAt": "2026-01-02",
}

ISSUES_DATA = {
    "data": {
        "issues": {
            "nodes": [ISSUE_NODE],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        }
    }
}

ISSUE_DETAIL_DATA = {
    "data": {
        "issue": {
            **ISSUE_NODE,
            "description": "Fix the bug",
            "team": {"key": "PLAT"},
            "comments": {"nodes": []},
        }
    }
}


@pytest.fixture(autouse=True)
def _fake_client():
    with patch(
        "agent_kit.linear.cli._get_client",
        return_value=__import__("agent_kit.linear.client", fromlist=["LinearClient"]).LinearClient("fake"),
    ):
        yield



class TestTeamsCommand:
    @respx.mock
    def test_lists_teams(self, cli_runner):
        respx.post(LINEAR_API).mock(return_value=Response(200, json=TEAMS_DATA))
        result = cli_runner.invoke(linear, ["teams"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["key"] == "PLAT"


class TestTeamCommand:
    @respx.mock
    def test_gets_team(self, cli_runner):
        respx.post(LINEAR_API).mock(return_value=Response(200, json=TEAM_DATA))
        result = cli_runner.invoke(linear, ["team", "PLAT"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["key"] == "PLAT"


class TestIssuesCommand:
    @respx.mock
    def test_lists_issues(self, cli_runner):
        # First call: resolve team, second: get issues
        respx.post(LINEAR_API).mock(
            side_effect=[
                Response(200, json=TEAM_DATA),
                Response(200, json=ISSUES_DATA),
            ]
        )
        result = cli_runner.invoke(linear, ["issues", "--team", "PLAT"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["identifier"] == "PLAT-1"


class TestIssueCommand:
    @respx.mock
    def test_gets_issue(self, cli_runner):
        respx.post(LINEAR_API).mock(return_value=Response(200, json=ISSUE_DETAIL_DATA))
        result = cli_runner.invoke(linear, ["issue", "PLAT-1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["identifier"] == "PLAT-1"
        assert data["description"] == "Fix the bug"
