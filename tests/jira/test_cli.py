"""Tests for agent_kit.jira.cli."""

import json
from unittest.mock import patch

import respx
from httpx import Response

from agent_kit.jira.cli import jira
from agent_kit.jira.client import JiraClient

BASE_URL = "https://api.atlassian.com/ex/jira/cloud123/rest/api/3"

PROJECT_DATA = {
    "id": "1",
    "key": "PLAT",
    "name": "Platform",
    "projectTypeKey": "software",
    "issueTypes": [{"id": "t1", "name": "Bug", "subtask": False}],
}

SAMPLE_ISSUE = {
    "key": "PLAT-1",
    "fields": {
        "summary": "Fix bug",
        "status": {"name": "To Do"},
        "assignee": {"displayName": "Alice"},
        "priority": {"name": "High"},
        "issuetype": {"name": "Bug"},
        "labels": ["backend"],
        "created": "2026-01-01",
        "updated": "2026-01-02",
    },
}

SAMPLE_ISSUE_DETAIL = {
    **SAMPLE_ISSUE,
    "fields": {
        **SAMPLE_ISSUE["fields"],
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Fix the bug"}]}
            ],
        },
        "project": {"key": "PLAT"},
        "comment": {"comments": []},
    },
}


def _fake_client() -> JiraClient:
    return JiraClient("test@co.com", "tok", "cloud123")


@respx.mock
def _mock_get_client():
    return _fake_client()


class TestProjectsCommand:
    @respx.mock
    def test_lists_projects(self, cli_runner):
        with patch("agent_kit.jira.cli._get_client", return_value=_fake_client()):
            respx.get(f"{BASE_URL}/project/search").mock(
                return_value=Response(
                    200,
                    json={"values": [{"id": "1", "key": "PLAT", "name": "Platform", "projectTypeKey": "software"}]},
                )
            )
            result = cli_runner.invoke(jira, ["projects"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["key"] == "PLAT"


class TestProjectCommand:
    @respx.mock
    def test_gets_project(self, cli_runner):
        with patch("agent_kit.jira.cli._get_client", return_value=_fake_client()):
            respx.get(f"{BASE_URL}/project/PLAT").mock(
                return_value=Response(200, json=PROJECT_DATA)
            )
            result = cli_runner.invoke(jira, ["project", "PLAT"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["key"] == "PLAT"
        assert data["issueTypes"][0]["name"] == "Bug"


class TestStatusesCommand:
    @respx.mock
    def test_lists_statuses(self, cli_runner):
        with patch("agent_kit.jira.cli._get_client", return_value=_fake_client()):
            respx.get(f"{BASE_URL}/project/PLAT/statuses").mock(
                return_value=Response(
                    200,
                    json=[{"name": "Bug", "statuses": [{"id": "s1", "name": "To Do"}]}],
                )
            )
            result = cli_runner.invoke(jira, ["statuses", "PLAT"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["issueType"] == "Bug"


class TestIssuesCommand:
    @respx.mock
    def test_lists_issues(self, cli_runner):
        with patch("agent_kit.jira.cli._get_client", return_value=_fake_client()):
            respx.post(f"{BASE_URL}/search/jql").mock(
                return_value=Response(
                    200, json={"issues": [SAMPLE_ISSUE], "isLast": True}
                )
            )
            result = cli_runner.invoke(jira, ["issues", "--project", "PLAT"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["key"] == "PLAT-1"

    @respx.mock
    def test_with_jql(self, cli_runner):
        with patch("agent_kit.jira.cli._get_client", return_value=_fake_client()):
            respx.post(f"{BASE_URL}/search/jql").mock(
                return_value=Response(200, json={"issues": [], "isLast": True})
            )
            result = cli_runner.invoke(jira, ["issues", "--jql", "project = PLAT"])
        assert result.exit_code == 0
        assert json.loads(result.output) == []


class TestIssueCommand:
    @respx.mock
    def test_gets_issue(self, cli_runner):
        with patch("agent_kit.jira.cli._get_client", return_value=_fake_client()):
            respx.get(f"{BASE_URL}/issue/PLAT-1").mock(
                return_value=Response(200, json=SAMPLE_ISSUE_DETAIL)
            )
            result = cli_runner.invoke(jira, ["issue", "PLAT-1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["key"] == "PLAT-1"
        assert data["description"] == "Fix the bug"


class TestCreateIssueCommand:
    @respx.mock
    def test_creates_issue(self, cli_runner):
        with patch("agent_kit.jira.cli._get_client", return_value=_fake_client()):
            respx.post(f"{BASE_URL}/issue").mock(
                return_value=Response(200, json={"key": "PLAT-5", "id": "5", "self": "url"})
            )
            result = cli_runner.invoke(
                jira, ["create-issue", "--project", "PLAT", "--summary", "New bug", "--type", "Bug"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["key"] == "PLAT-5"


class TestUpdateIssueCommand:
    @respx.mock
    def test_updates_issue(self, cli_runner):
        with patch("agent_kit.jira.cli._get_client", return_value=_fake_client()):
            respx.put(f"{BASE_URL}/issue/PLAT-1").mock(return_value=Response(204))
            respx.get(f"{BASE_URL}/issue/PLAT-1").mock(
                return_value=Response(200, json=SAMPLE_ISSUE_DETAIL)
            )
            result = cli_runner.invoke(
                jira, ["update-issue", "PLAT-1", "--summary", "Updated"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["key"] == "PLAT-1"


class TestTransitionCommand:
    @respx.mock
    def test_transitions_issue(self, cli_runner):
        with patch("agent_kit.jira.cli._get_client", return_value=_fake_client()):
            respx.get(f"{BASE_URL}/issue/PLAT-1/transitions").mock(
                return_value=Response(
                    200, json={"transitions": [{"id": "t1", "name": "Done"}]}
                )
            )
            respx.post(f"{BASE_URL}/issue/PLAT-1/transitions").mock(
                return_value=Response(204)
            )
            respx.get(f"{BASE_URL}/issue/PLAT-1").mock(
                return_value=Response(200, json=SAMPLE_ISSUE_DETAIL)
            )
            result = cli_runner.invoke(jira, ["transition", "PLAT-1", "--status", "Done"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["key"] == "PLAT-1"


class TestCommentsCommand:
    @respx.mock
    def test_lists_comments(self, cli_runner):
        with patch("agent_kit.jira.cli._get_client", return_value=_fake_client()):
            respx.get(f"{BASE_URL}/issue/PLAT-1/comment").mock(
                return_value=Response(
                    200,
                    json={
                        "comments": [
                            {
                                "id": "c1",
                                "author": {"displayName": "Alice"},
                                "body": {
                                    "type": "doc",
                                    "version": 1,
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [{"type": "text", "text": "Hi"}],
                                        }
                                    ],
                                },
                                "created": "2026-01-01",
                            }
                        ]
                    },
                )
            )
            result = cli_runner.invoke(jira, ["comments", "PLAT-1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["body"] == "Hi"


class TestCommentCommand:
    @respx.mock
    def test_adds_comment(self, cli_runner):
        with patch("agent_kit.jira.cli._get_client", return_value=_fake_client()):
            respx.post(f"{BASE_URL}/issue/PLAT-1/comment").mock(
                return_value=Response(
                    200,
                    json={
                        "id": "c2",
                        "author": {"displayName": "Bob"},
                        "body": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "LGTM"}],
                                }
                            ],
                        },
                        "created": "2026-01-02",
                    },
                )
            )
            result = cli_runner.invoke(jira, ["comment", "PLAT-1", "-m", "LGTM"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["body"] == "LGTM"

    def test_no_message_fails(self, cli_runner):
        with patch("agent_kit.jira.cli._get_client", return_value=_fake_client()):
            result = cli_runner.invoke(jira, ["comment", "PLAT-1"])
        assert result.exit_code != 0
