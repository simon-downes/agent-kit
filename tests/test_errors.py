"""Tests for agent_kit.errors."""

import json

import httpx
import pytest

from agent_kit.errors import (
    AgentKitError,
    AuthError,
    ConfigError,
    ScopeError,
    handle_errors,
    output,
)


class TestOutput:
    def test_writes_json_to_stdout(self, capsys):
        output({"key": "value"})
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {"key": "value"}

    def test_list_output(self, capsys):
        output([1, 2, 3])
        assert json.loads(capsys.readouterr().out) == [1, 2, 3]


def _make_response(status_code, headers=None, text=""):
    """Build a minimal httpx.Response for testing."""
    return httpx.Response(status_code, headers=headers or {}, text=text)


def _make_http_error(status_code, headers=None, text=""):
    resp = _make_response(status_code, headers, text)
    return httpx.HTTPStatusError("error", request=httpx.Request("GET", "http://x"), response=resp)


class TestHandleErrors:
    def test_auth_error_exits_2(self, capsys):
        @handle_errors
        def fn():
            raise AuthError("bad creds")

        with pytest.raises(SystemExit) as exc_info:
            fn()
        assert exc_info.value.code == 2
        assert "bad creds" in capsys.readouterr().err

    def test_config_error_exits_1(self, capsys):
        @handle_errors
        def fn():
            raise ConfigError("bad config")

        with pytest.raises(SystemExit) as exc_info:
            fn()
        assert exc_info.value.code == 1
        assert "bad config" in capsys.readouterr().err

    def test_scope_error_exits_1(self, capsys):
        @handle_errors
        def fn():
            raise ScopeError("out of scope")

        with pytest.raises(SystemExit) as exc_info:
            fn()
        assert exc_info.value.code == 1

    def test_generic_agent_kit_error_exits_1(self, capsys):
        @handle_errors
        def fn():
            raise AgentKitError("generic")

        with pytest.raises(SystemExit) as exc_info:
            fn()
        assert exc_info.value.code == 1

    def test_http_401_exits_2(self, capsys):
        @handle_errors
        def fn():
            raise _make_http_error(401)

        with pytest.raises(SystemExit) as exc_info:
            fn()
        assert exc_info.value.code == 2
        assert "authentication failed" in capsys.readouterr().err

    def test_http_403_exits_2(self, capsys):
        @handle_errors
        def fn():
            raise _make_http_error(403)

        with pytest.raises(SystemExit) as exc_info:
            fn()
        assert exc_info.value.code == 2

    def test_http_429_exits_1_with_retry_after(self, capsys):
        @handle_errors
        def fn():
            raise _make_http_error(429, headers={"Retry-After": "30"}, text='{"ok":false}')

        with pytest.raises(SystemExit) as exc_info:
            fn()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "rate limit" in err
        assert "30" in err

    def test_http_500_exits_1(self, capsys):
        @handle_errors
        def fn():
            raise _make_http_error(500, text="server error")

        with pytest.raises(SystemExit) as exc_info:
            fn()
        assert exc_info.value.code == 1
        assert "500" in capsys.readouterr().err

    def test_value_error_exits_1(self, capsys):
        @handle_errors
        def fn():
            raise ValueError("bad value")

        with pytest.raises(SystemExit) as exc_info:
            fn()
        assert exc_info.value.code == 1
        assert "bad value" in capsys.readouterr().err

    def test_file_not_found_exits_1(self, capsys):
        @handle_errors
        def fn():
            raise FileNotFoundError("missing")

        with pytest.raises(SystemExit) as exc_info:
            fn()
        assert exc_info.value.code == 1

    def test_exception_group_unwraps(self, capsys):
        @handle_errors
        def fn():
            raise ExceptionGroup("group", [AuthError("nested")])

        with pytest.raises(SystemExit) as exc_info:
            fn()
        assert exc_info.value.code == 2
        assert "nested" in capsys.readouterr().err

    def test_exception_group_unhandled_type(self, capsys):
        @handle_errors
        def fn():
            raise ExceptionGroup("group", [RuntimeError("boom")])

        with pytest.raises(SystemExit) as exc_info:
            fn()
        assert exc_info.value.code == 1
        assert "boom" in capsys.readouterr().err

    def test_successful_function_returns_value(self):
        @handle_errors
        def fn():
            return 42

        assert fn() == 42
