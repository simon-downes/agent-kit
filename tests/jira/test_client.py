"""Tests for agent_kit.jira.client and resolve."""

import pytest
import respx
from httpx import Response

from agent_kit.jira.client import JiraClient, adf_to_text, text_to_adf
from agent_kit.jira.resolve import resolve_assignee, resolve_transition

BASE_URL = "https://api.atlassian.com/ex/jira/cloud123/rest/api/3"


def _client() -> JiraClient:
    return JiraClient("test@co.com", "tok", "cloud123")


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
        "comment": {
            "comments": [
                {
                    "author": {"displayName": "Bob"},
                    "body": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "LGTM"}]}
                        ],
                    },
                    "created": "2026-01-03",
                }
            ]
        },
    },
}


# --- ADF conversion ---


class TestAdfToText:
    def test_paragraph(self):
        doc = {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "hello"}]}
            ],
        }
        assert adf_to_text(doc) == "hello"

    def test_heading(self):
        doc = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Title"}],
                }
            ],
        }
        assert adf_to_text(doc) == "## Title"

    def test_bullet_list(self):
        doc = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "item one"}],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        assert "- item one" in adf_to_text(doc)

    def test_code_block(self):
        doc = {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "codeBlock", "content": [{"type": "text", "text": "x = 1"}]}
            ],
        }
        assert "```\nx = 1\n```" in adf_to_text(doc)

    def test_blockquote(self):
        doc = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "blockquote",
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "quoted"}]}
                    ],
                }
            ],
        }
        assert "> quoted" in adf_to_text(doc)

    def test_none_returns_empty(self):
        assert adf_to_text(None) == ""

    def test_empty_dict_returns_empty(self):
        assert adf_to_text({}) == ""

    def test_hard_break(self):
        doc = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "line1"},
                        {"type": "hardBreak"},
                        {"type": "text", "text": "line2"},
                    ],
                }
            ],
        }
        assert adf_to_text(doc) == "line1\nline2"


class TestTextToAdf:
    def test_single_line(self):
        result = text_to_adf("hello")
        assert result["type"] == "doc"
        assert result["version"] == 1
        assert len(result["content"]) == 1
        assert result["content"][0]["content"][0]["text"] == "hello"

    def test_empty_string(self):
        result = text_to_adf("")
        assert len(result["content"]) == 1
        assert result["content"][0]["content"] == []

    def test_multiline(self):
        result = text_to_adf("line1\nline2")
        assert len(result["content"]) == 2


# --- JiraClient ---


class TestJiraClient:
    @respx.mock
    def test_get(self):
        respx.get(f"{BASE_URL}/project/search").mock(
            return_value=Response(200, json={"values": []})
        )
        result = _client().get("/project/search")
        assert result == {"values": []}

    @respx.mock
    def test_post(self):
        respx.post(f"{BASE_URL}/issue").mock(
            return_value=Response(200, json={"key": "PLAT-1", "id": "1"})
        )
        result = _client().post("/issue", json={"fields": {}})
        assert result["key"] == "PLAT-1"

    @respx.mock
    def test_put_204(self):
        respx.put(f"{BASE_URL}/issue/PLAT-1").mock(return_value=Response(204))
        result = _client().put("/issue/PLAT-1", json={"fields": {}})
        assert result == {}

    @respx.mock
    def test_401_raises(self):
        respx.get(f"{BASE_URL}/myself").mock(return_value=Response(401))
        with pytest.raises(Exception):
            _client().get("/myself")

    @respx.mock
    def test_429_raises(self):
        respx.get(f"{BASE_URL}/myself").mock(return_value=Response(429))
        with pytest.raises(Exception, match="rate limit"):
            _client().get("/myself")

    @respx.mock
    def test_api_error_with_messages(self):
        respx.post(f"{BASE_URL}/issue").mock(
            return_value=Response(
                400, json={"errorMessages": ["bad field"], "errors": {"summary": "required"}}
            )
        )
        with pytest.raises(ValueError, match="bad field.*summary: required"):
            _client().post("/issue", json={})

    @respx.mock
    def test_api_error_no_json(self):
        respx.post(f"{BASE_URL}/issue").mock(return_value=Response(400, text="bad"))
        with pytest.raises(Exception):
            _client().post("/issue", json={})


# --- Project queries ---


class TestGetProjects:
    @respx.mock
    def test_returns_projects(self):
        respx.get(f"{BASE_URL}/project/search").mock(
            return_value=Response(
                200,
                json={"values": [{"id": "1", "key": "PLAT", "name": "Platform", "projectTypeKey": "software"}]},
            )
        )
        result = _client().get_projects()
        assert len(result) == 1
        assert result[0]["key"] == "PLAT"


class TestGetProject:
    @respx.mock
    def test_returns_detail(self):
        respx.get(f"{BASE_URL}/project/PLAT").mock(
            return_value=Response(
                200,
                json={
                    "id": "1",
                    "key": "PLAT",
                    "name": "Platform",
                    "projectTypeKey": "software",
                    "issueTypes": [{"id": "t1", "name": "Bug", "subtask": False}],
                },
            )
        )
        result = _client().get_project("PLAT")
        assert result["key"] == "PLAT"
        assert result["issueTypes"][0]["name"] == "Bug"


class TestGetStatuses:
    @respx.mock
    def test_returns_statuses(self):
        respx.get(f"{BASE_URL}/project/PLAT/statuses").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "name": "Bug",
                        "statuses": [{"id": "s1", "name": "To Do"}, {"id": "s2", "name": "Done"}],
                    }
                ],
            )
        )
        result = _client().get_statuses("PLAT")
        assert result[0]["issueType"] == "Bug"
        assert len(result[0]["statuses"]) == 2


# --- Issue queries ---


class TestSearchIssues:
    @respx.mock
    def test_single_page(self):
        respx.post(f"{BASE_URL}/search/jql").mock(
            return_value=Response(
                200, json={"issues": [SAMPLE_ISSUE], "isLast": True}
            )
        )
        result = _client().search_issues(project="PLAT", limit=10)
        assert len(result) == 1
        assert result[0]["key"] == "PLAT-1"

    @respx.mock
    def test_pagination(self):
        respx.post(f"{BASE_URL}/search/jql").mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "issues": [SAMPLE_ISSUE],
                        "isLast": False,
                        "nextPageToken": "page2",
                    },
                ),
                Response(
                    200,
                    json={
                        "issues": [{**SAMPLE_ISSUE, "key": "PLAT-2"}],
                        "isLast": True,
                    },
                ),
            ]
        )
        result = _client().search_issues(project="PLAT", limit=10)
        assert len(result) == 2

    @respx.mock
    def test_respects_limit(self):
        respx.post(f"{BASE_URL}/search/jql").mock(
            return_value=Response(
                200,
                json={
                    "issues": [SAMPLE_ISSUE, {**SAMPLE_ISSUE, "key": "PLAT-2"}],
                    "isLast": False,
                    "nextPageToken": "more",
                },
            )
        )
        result = _client().search_issues(project="PLAT", limit=1)
        assert len(result) == 1

    @respx.mock
    def test_raw_jql(self):
        route = respx.post(f"{BASE_URL}/search/jql").mock(
            return_value=Response(200, json={"issues": [], "isLast": True})
        )
        _client().search_issues(jql="project = PLAT AND sprint in openSprints()")
        body = route.calls[0].request.content
        assert b"openSprints" in body


class TestGetIssue:
    @respx.mock
    def test_returns_detail(self):
        respx.get(f"{BASE_URL}/issue/PLAT-1").mock(
            return_value=Response(200, json=SAMPLE_ISSUE_DETAIL)
        )
        result = _client().get_issue("PLAT-1")
        assert result["key"] == "PLAT-1"
        assert result["description"] == "Fix the bug"
        assert result["project"] == "PLAT"
        assert len(result["comments"]) == 1
        assert result["comments"][0]["author"] == "Bob"

    @respx.mock
    def test_null_fields(self):
        issue = {
            "key": "PLAT-2",
            "fields": {
                "summary": "Test",
                "status": None,
                "assignee": None,
                "priority": None,
                "issuetype": None,
                "labels": [],
                "created": None,
                "updated": None,
                "description": None,
                "project": None,
                "comment": {"comments": []},
            },
        }
        respx.get(f"{BASE_URL}/issue/PLAT-2").mock(
            return_value=Response(200, json=issue)
        )
        result = _client().get_issue("PLAT-2")
        assert result["status"] is None
        assert result["assignee"] is None
        assert result["description"] == ""


# --- Issue mutations ---


class TestCreateIssue:
    @respx.mock
    def test_creates(self):
        respx.post(f"{BASE_URL}/issue").mock(
            return_value=Response(200, json={"key": "PLAT-3", "id": "3", "self": "url"})
        )
        result = _client().create_issue(project_key="PLAT", summary="New", issue_type="Task")
        assert result["key"] == "PLAT-3"

    @respx.mock
    def test_with_description(self):
        route = respx.post(f"{BASE_URL}/issue").mock(
            return_value=Response(200, json={"key": "PLAT-4", "id": "4"})
        )
        _client().create_issue(
            project_key="PLAT", summary="New", issue_type="Task", description="desc"
        )
        body = route.calls[0].request.content
        assert b"description" in body


class TestUpdateIssue:
    @respx.mock
    def test_updates_and_returns(self):
        respx.put(f"{BASE_URL}/issue/PLAT-1").mock(return_value=Response(204))
        respx.get(f"{BASE_URL}/issue/PLAT-1").mock(
            return_value=Response(200, json=SAMPLE_ISSUE_DETAIL)
        )
        result = _client().update_issue("PLAT-1", summary="Updated")
        assert result["key"] == "PLAT-1"


class TestTransitionIssue:
    @respx.mock
    def test_transitions(self):
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
        result = _client().transition_issue("PLAT-1", transition_id="t1")
        assert result["key"] == "PLAT-1"


# --- Comments ---


class TestGetComments:
    @respx.mock
    def test_returns_comments(self):
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
                                        "content": [{"type": "text", "text": "Nice"}],
                                    }
                                ],
                            },
                            "created": "2026-01-01",
                        }
                    ]
                },
            )
        )
        result = _client().get_comments("PLAT-1")
        assert len(result) == 1
        assert result[0]["body"] == "Nice"


class TestCreateComment:
    @respx.mock
    def test_creates(self):
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
                            {"type": "paragraph", "content": [{"type": "text", "text": "Done"}]}
                        ],
                    },
                    "created": "2026-01-02",
                },
            )
        )
        result = _client().create_comment("PLAT-1", body="Done")
        assert result["id"] == "c2"
        assert result["body"] == "Done"


# --- Users ---


class TestSearchUsers:
    @respx.mock
    def test_filters_atlassian_users(self):
        respx.get(f"{BASE_URL}/user/search").mock(
            return_value=Response(
                200,
                json=[
                    {"accountId": "u1", "displayName": "Alice", "accountType": "atlassian"},
                    {"accountId": "u2", "displayName": "Bot", "accountType": "app"},
                ],
            )
        )
        result = _client().search_users("alice")
        assert len(result) == 1
        assert result[0]["accountId"] == "u1"


# --- Resolve ---


class TestResolveAssignee:
    @respx.mock
    def test_partial_match(self):
        respx.get(f"{BASE_URL}/user/search").mock(
            return_value=Response(
                200,
                json=[
                    {"accountId": "u1", "displayName": "Alice Smith", "accountType": "atlassian"},
                    {"accountId": "u2", "displayName": "Bob", "accountType": "atlassian"},
                ],
            )
        )
        assert resolve_assignee(_client(), "alice") == "u1"

    @respx.mock
    def test_fallback_to_first(self):
        respx.get(f"{BASE_URL}/user/search").mock(
            return_value=Response(
                200,
                json=[
                    {"accountId": "u1", "displayName": "Charlie", "accountType": "atlassian"},
                ],
            )
        )
        assert resolve_assignee(_client(), "xyz") == "u1"

    @respx.mock
    def test_not_found(self):
        respx.get(f"{BASE_URL}/user/search").mock(
            return_value=Response(200, json=[])
        )
        with pytest.raises(ValueError, match="not found"):
            resolve_assignee(_client(), "nobody")


class TestResolveTransition:
    @respx.mock
    def test_case_insensitive(self):
        respx.get(f"{BASE_URL}/issue/PLAT-1/transitions").mock(
            return_value=Response(
                200, json={"transitions": [{"id": "t1", "name": "Done"}, {"id": "t2", "name": "In Progress"}]}
            )
        )
        assert resolve_transition(_client(), "PLAT-1", "done") == "t1"

    @respx.mock
    def test_not_found(self):
        respx.get(f"{BASE_URL}/issue/PLAT-1/transitions").mock(
            return_value=Response(
                200, json={"transitions": [{"id": "t1", "name": "Done"}]}
            )
        )
        with pytest.raises(ValueError, match="Available"):
            resolve_transition(_client(), "PLAT-1", "nonexistent")


# --- Attachments ---


class TestAttachFile:
    @respx.mock
    def test_attaches_file(self, tmp_path):
        f = tmp_path / "screenshot.png"
        f.write_bytes(b"fake-png")
        respx.post(f"{BASE_URL}/issue/PLAT-1/attachments").mock(
            return_value=Response(
                200,
                json=[{"id": "a1", "filename": "screenshot.png", "size": 8, "content": "url"}],
            )
        )
        result = _client().attach_file("PLAT-1", str(f))
        assert len(result) == 1
        assert result[0]["filename"] == "screenshot.png"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            _client().attach_file("PLAT-1", "/nonexistent/file.txt")
