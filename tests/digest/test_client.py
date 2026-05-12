"""Tests for session digest client."""

import json
import time
from pathlib import Path
from unittest.mock import patch

import yaml

from agent_kit.digest.client import DigestClient

# --- Fixtures ---

SESSION_META = {
    "session_id": "abc-123",
    "cwd": "/home/user/dev/myproject",
    "created_at": "2026-05-09T14:30:00.123456789Z",
    "updated_at": "2026-05-09T17:10:00.987654321Z",
    "title": "test session",
    "session_state": {"agent_name": "archie"},
}

SUBAGENT_META = {
    "session_id": "sub-456",
    "cwd": "/home/user/dev/myproject",
    "created_at": "2026-05-09T14:30:00Z",
    "updated_at": "2026-05-09T14:35:00Z",
    "title": "subagent",
    "session_state": {},
}


def _prompt(message_id: str, text: str, timestamp: int) -> dict:
    return {
        "version": "v1",
        "kind": "Prompt",
        "data": {
            "message_id": message_id,
            "content": [{"kind": "text", "data": text}],
            "meta": {"timestamp": timestamp},
        },
    }


def _assistant_text(message_id: str, text: str) -> dict:
    return {
        "version": "v1",
        "kind": "AssistantMessage",
        "data": {
            "message_id": message_id,
            "content": [{"kind": "text", "data": text}],
        },
    }


def _assistant_with_tools(message_id: str, text: str, tools: list[dict]) -> dict:
    content = [{"kind": "text", "data": text}]
    for tool in tools:
        content.append({"kind": "toolUse", "data": tool})
    return {
        "version": "v1",
        "kind": "AssistantMessage",
        "data": {"message_id": message_id, "content": content},
    }


def _tool_results(message_id: str, results: list[dict]) -> dict:
    content = []
    for r in results:
        content.append({"kind": "toolResult", "data": r})
    return {
        "version": "v1",
        "kind": "ToolResults",
        "data": {"message_id": message_id, "content": content},
    }


def _write_session(tmp_path: Path, meta: dict, entries: list[dict]) -> tuple[Path, Path]:
    """Write session files and return (json_path, jsonl_path)."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    sid = meta["session_id"]
    json_path = sessions_dir / f"{sid}.json"
    jsonl_path = sessions_dir / f"{sid}.jsonl"
    json_path.write_text(json.dumps(meta))
    jsonl_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return sessions_dir, tmp_path / "output"


MOCK_CONFIG = {"project_dir": "/home/user/dev", "brain": {"dir": "/tmp/brain"}, "agent": "archie"}

PATCH_CONFIG = "agent_kit.digest.client.load_config"


# --- Tests ---


class TestTurnSplitting:
    def test_single_turn(self, tmp_path):
        entries = [
            _prompt("p1", "hello", 1715270000),
            _assistant_text("a1", "hi there"),
        ]
        sessions_dir, output_dir = _write_session(tmp_path, SESSION_META, entries)

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            client.digest_session("abc-123")

        output = list(output_dir.glob("*.yaml"))[0]
        data = yaml.safe_load(output.read_text())
        assert len(data["turns"]) == 1
        assert data["turns"][0]["user"] == "hello"
        assert data["turns"][0]["assistant"] == "hi there"

    def test_multiple_turns(self, tmp_path):
        entries = [
            _prompt("p1", "first question", 1715270000),
            _assistant_text("a1", "first answer"),
            _prompt("p2", "second question", 1715270060),
            _assistant_text("a2", "second answer"),
        ]
        sessions_dir, output_dir = _write_session(tmp_path, SESSION_META, entries)

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            client.digest_session("abc-123")

        output = list(output_dir.glob("*.yaml"))[0]
        data = yaml.safe_load(output.read_text())
        assert len(data["turns"]) == 2
        assert data["turns"][0]["user"] == "first question"
        assert data["turns"][1]["user"] == "second question"

    def test_empty_session_produces_no_output(self, tmp_path):
        sessions_dir, output_dir = _write_session(tmp_path, SESSION_META, [])

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            client.digest_session("abc-123")

        assert list(output_dir.glob("*.yaml")) == []


class TestAssistantTextExtraction:
    def test_strips_tool_use_blocks(self, tmp_path):
        entries = [
            _prompt("p1", "do something", 1715270000),
            _assistant_with_tools(
                "a1",
                "Let me check that.",
                [
                    {
                        "toolUseId": "t1",
                        "name": "read",
                        "input": {"operations": [{"path": "/tmp/f"}]},
                    }
                ],
            ),
            _tool_results(
                "r1",
                [
                    {
                        "toolUseId": "t1",
                        "status": "success",
                        "content": [{"kind": "text", "data": "file contents here..."}],
                    }
                ],
            ),
            _assistant_text("a2", "Based on the file, here's my answer."),
        ]
        sessions_dir, output_dir = _write_session(tmp_path, SESSION_META, entries)

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            client.digest_session("abc-123")

        data = yaml.safe_load(list(output_dir.glob("*.yaml"))[0].read_text())
        assistant = data["turns"][0]["assistant"]
        assert "Let me check that." in assistant
        assert "Based on the file" in assistant
        assert "file contents here" not in assistant

    def test_trims_to_2000_chars(self, tmp_path):
        long_text = "x" * 3000
        entries = [
            _prompt("p1", "question", 1715270000),
            _assistant_text("a1", long_text),
        ]
        sessions_dir, output_dir = _write_session(tmp_path, SESSION_META, entries)

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            client.digest_session("abc-123")

        data = yaml.safe_load(list(output_dir.glob("*.yaml"))[0].read_text())
        assert len(data["turns"][0]["assistant"]) == 2000


class TestTargetExtraction:
    def test_read_target(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        target = client._extract_target("read", {"operations": [{"path": "/home/user/file.py"}]})
        assert target == "/home/user/file.py"

    def test_write_target(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        target = client._extract_target(
            "write", {"path": "/home/user/file.py", "command": "create"}
        )
        assert target == "/home/user/file.py"

    def test_shell_target_not_truncated(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        long_cmd = "x" * 300
        target = client._extract_target("shell", {"command": long_cmd})
        assert len(target) == 300

    def test_glob_target(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        target = client._extract_target("glob", {"pattern": "**/*.py"})
        assert target == "**/*.py"

    def test_grep_target(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        target = client._extract_target("grep", {"pattern": "def main"})
        assert target == "def main"

    def test_web_search_target(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        target = client._extract_target("web_search", {"query": "python yaml"})
        assert target == "python yaml"

    def test_use_aws_target(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        target = client._extract_target(
            "use_aws", {"service_name": "s3", "operation_name": "list-buckets"}
        )
        assert target == "s3 list-buckets"

    def test_subagent_target_truncated(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        long_task = "y" * 200
        target = client._extract_target("subagent", {"task": long_task})
        assert len(target) == 100

    def test_unknown_tool_fallback(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        target = client._extract_target("custom_tool", {"query": "something", "limit": 5})
        assert target == "something"

    def test_introspect_target(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        target = client._extract_target("introspect", {"query": "/spawn command"})
        assert target == "/spawn command"


class TestErrorExtraction:
    def test_validation_error(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        result = {
            "toolUseId": "t1",
            "status": "error",
            "content": [{"kind": "text", "data": "The provided old_str was not found in the file"}],
        }
        error = client._extract_error(result)
        assert error == "The provided old_str was not found in the file"

    def test_shell_error(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        result = {
            "toolUseId": "t1",
            "status": "error",
            "content": [
                {
                    "kind": "json",
                    "data": {
                        "exit_status": "exit status: 1",
                        "stderr": "No module named ruff\nsome other line",
                        "stdout": "",
                    },
                }
            ],
        }
        error = client._extract_error(result)
        assert "exit status: 1" in error
        assert "No module named ruff" in error
        assert "some other line" not in error

    def test_error_truncated(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        long_error = "e" * 1000
        result = {
            "toolUseId": "t1",
            "status": "error",
            "content": [{"kind": "text", "data": long_error}],
        }
        error = client._extract_error(result)
        assert len(error) == 500

    def test_no_error_on_success(self, tmp_path):
        entries = [
            _prompt("p1", "do it", 1715270000),
            _assistant_with_tools(
                "a1",
                "Running.",
                [{"toolUseId": "t1", "name": "shell", "input": {"command": "echo hi"}}],
            ),
            _tool_results(
                "r1",
                [
                    {
                        "toolUseId": "t1",
                        "status": "success",
                        "content": [
                            {
                                "kind": "json",
                                "data": {
                                    "exit_status": "exit status: 0",
                                    "stdout": "hi",
                                    "stderr": "",
                                },
                            }
                        ],
                    }
                ],
            ),
        ]
        sessions_dir, output_dir = _write_session(tmp_path, SESSION_META, entries)

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            client.digest_session("abc-123")

        data = yaml.safe_load(list(output_dir.glob("*.yaml"))[0].read_text())
        tool = data["turns"][0]["tools"][0]
        assert tool["success"] is True
        assert "error" not in tool


class TestSessionFiltering:
    def test_skips_subagent_sessions(self, tmp_path):
        entries = [
            _prompt("p1", "hello", 1715270000),
            _assistant_text("a1", "hi"),
        ]
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        json_path = sessions_dir / "sub-456.json"
        jsonl_path = sessions_dir / "sub-456.jsonl"
        json_path.write_text(json.dumps(SUBAGENT_META))
        jsonl_path.write_text("\n".join(json.dumps(e) for e in entries))

        output_dir = tmp_path / "output"

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            result = client.digest_all()

        assert result["skipped"] == 1
        assert result["processed"] == 0

    def test_skips_sessions_without_jsonl(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        (sessions_dir / "abc-123.json").write_text(json.dumps(SESSION_META))
        # No .jsonl file

        output_dir = tmp_path / "output"

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            result = client.digest_all()

        assert result["processed"] == 0


class TestFreshnessCheck:
    def test_processes_when_no_output_exists(self, tmp_path):
        entries = [
            _prompt("p1", "hello", 1715270000),
            _assistant_text("a1", "hi"),
        ]
        sessions_dir, output_dir = _write_session(tmp_path, SESSION_META, entries)

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            result = client.digest_all()

        assert result["processed"] == 1

    def test_skips_when_output_is_fresh(self, tmp_path):
        entries = [
            _prompt("p1", "hello", 1715270000),
            _assistant_text("a1", "hi"),
        ]
        sessions_dir, output_dir = _write_session(tmp_path, SESSION_META, entries)

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            client.digest_all()
            # Run again — should skip
            result = client.digest_all()

        assert result["skipped"] == 1
        assert result["processed"] == 0

    def test_reprocesses_when_source_is_newer(self, tmp_path):
        entries = [
            _prompt("p1", "hello", 1715270000),
            _assistant_text("a1", "hi"),
        ]
        sessions_dir, output_dir = _write_session(tmp_path, SESSION_META, entries)

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            client.digest_all()

            # Touch the source to make it newer
            time.sleep(0.05)
            jsonl_path = sessions_dir / "abc-123.jsonl"
            jsonl_path.write_text(jsonl_path.read_text())

            result = client.digest_all()

        assert result["processed"] == 1


class TestProjectResolution:
    def test_resolves_project_from_cwd(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            assert client._resolve_project("/home/user/dev/myproject") == "myproject"
            assert client._resolve_project("/home/user/dev/archie") == "archie"

    def test_general_when_outside_project_dir(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            assert client._resolve_project("/tmp/something") == "general"

    def test_general_when_empty_cwd(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            assert client._resolve_project("") == "general"


class TestTimestampFormatting:
    def test_iso_with_nanoseconds(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        result = client._format_iso("2026-05-09T14:30:00.123456789Z")
        assert result == "2026-05-09 14:30:00"

    def test_iso_with_timezone(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        result = client._format_iso("2026-05-09T14:30:00.123+00:00")
        assert result == "2026-05-09 14:30:00"

    def test_unix_timestamp(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        result = client._format_timestamp(1715270000)
        assert result == "2024-05-09 15:53:20"

    def test_none_timestamp(self, tmp_path):
        client = DigestClient(tmp_path, tmp_path)
        assert client._format_timestamp(None) == ""
        assert client._format_iso("") == ""


class TestOutputFormat:
    def test_full_output_structure(self, tmp_path):
        entries = [
            _prompt("p1", "check the file", 1715270000),
            _assistant_with_tools(
                "a1",
                "Let me read that.",
                [
                    {
                        "toolUseId": "t1",
                        "name": "read",
                        "input": {"operations": [{"mode": "Line", "path": "/tmp/test.py"}]},
                    }
                ],
            ),
            _tool_results(
                "r1",
                [
                    {
                        "toolUseId": "t1",
                        "status": "success",
                        "content": [{"kind": "text", "data": "def main(): pass"}],
                    }
                ],
            ),
            _assistant_text("a2", "The file contains a main function."),
        ]
        sessions_dir, output_dir = _write_session(tmp_path, SESSION_META, entries)

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            client.digest_session("abc-123")

        output = list(output_dir.glob("*.yaml"))[0]
        data = yaml.safe_load(output.read_text())

        assert data["session_id"] == "abc-123"
        assert data["project"] == "myproject"
        assert data["started"] == "2026-05-09 14:30:00"
        assert data["ended"] == "2026-05-09 17:10:00"

        turn = data["turns"][0]
        assert turn["prompt_id"] == "p1"
        assert turn["user"] == "check the file"
        assert "Let me read that" in turn["assistant"]
        assert "def main" not in turn["assistant"]

        tool = turn["tools"][0]
        assert tool["id"] == "t1"
        assert tool["name"] == "read"
        assert tool["target"] == "/tmp/test.py"
        assert tool["success"] is True
        assert "error" not in tool

    def test_no_tools_key_when_empty(self, tmp_path):
        entries = [
            _prompt("p1", "what do you think?", 1715270000),
            _assistant_text("a1", "I think it's fine."),
        ]
        sessions_dir, output_dir = _write_session(tmp_path, SESSION_META, entries)

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            client.digest_session("abc-123")

        data = yaml.safe_load(list(output_dir.glob("*.yaml"))[0].read_text())
        assert "tools" not in data["turns"][0]

    def test_no_assistant_key_when_empty(self, tmp_path):
        """A prompt with no assistant response (e.g. session ended)."""
        entries = [
            _prompt("p1", "hello", 1715270000),
        ]
        sessions_dir, output_dir = _write_session(tmp_path, SESSION_META, entries)

        with patch("agent_kit.digest.client.load_config", return_value=MOCK_CONFIG):
            client = DigestClient(sessions_dir, output_dir)
            client.digest_session("abc-123")

        data = yaml.safe_load(list(output_dir.glob("*.yaml"))[0].read_text())
        assert "assistant" not in data["turns"][0]
