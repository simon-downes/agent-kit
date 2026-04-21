"""Tests for agent_kit.auth credential store."""

from unittest.mock import patch

import yaml

from agent_kit.auth import get_field, load_credentials, save_credentials, set_field, set_fields


class TestLoadCredentials:
    def test_returns_empty_when_missing(self, tmp_path):
        with patch("agent_kit.auth.CREDENTIALS_PATH", tmp_path / "nope.yaml"):
            assert load_credentials() == {}

    def test_loads_valid_file(self, tmp_path):
        creds_file = tmp_path / "creds.yaml"
        creds_file.write_text(yaml.dump({"slack": {"token": "xoxp-123"}}))
        creds_file.chmod(0o600)
        with patch("agent_kit.auth.CREDENTIALS_PATH", creds_file):
            assert load_credentials() == {"slack": {"token": "xoxp-123"}}

    def test_warns_on_permissive_permissions(self, tmp_path, capsys):
        creds_file = tmp_path / "creds.yaml"
        creds_file.write_text(yaml.dump({"a": 1}))
        creds_file.chmod(0o644)
        with patch("agent_kit.auth.CREDENTIALS_PATH", creds_file):
            load_credentials()
        assert "permissions" in capsys.readouterr().err

    def test_empty_file_returns_empty(self, tmp_path):
        creds_file = tmp_path / "creds.yaml"
        creds_file.write_text("")
        creds_file.chmod(0o600)
        with patch("agent_kit.auth.CREDENTIALS_PATH", creds_file):
            assert load_credentials() == {}


class TestSaveCredentials:
    def test_creates_file_with_permissions(self, tmp_path):
        creds_file = tmp_path / "creds.yaml"
        with (
            patch("agent_kit.auth.CREDENTIALS_PATH", creds_file),
            patch("agent_kit.auth.AGENT_KIT_HOME", tmp_path),
        ):
            save_credentials({"slack": {"token": "abc"}})
        assert creds_file.exists()
        loaded = yaml.safe_load(creds_file.read_text())
        assert loaded == {"slack": {"token": "abc"}}
        assert oct(creds_file.stat().st_mode & 0o777) == "0o600"


class TestGetField:
    def test_returns_value(self, tmp_path):
        creds_file = tmp_path / "creds.yaml"
        creds_file.write_text(yaml.dump({"slack": {"access_token": "xoxp-abc"}}))
        creds_file.chmod(0o600)
        with patch("agent_kit.auth.CREDENTIALS_PATH", creds_file):
            assert get_field("slack", "access_token") == "xoxp-abc"

    def test_returns_none_for_missing_service(self, tmp_path):
        creds_file = tmp_path / "creds.yaml"
        creds_file.write_text(yaml.dump({}))
        creds_file.chmod(0o600)
        with patch("agent_kit.auth.CREDENTIALS_PATH", creds_file):
            assert get_field("slack", "token") is None

    def test_returns_none_for_missing_field(self, tmp_path):
        creds_file = tmp_path / "creds.yaml"
        creds_file.write_text(yaml.dump({"slack": {"other": "val"}}))
        creds_file.chmod(0o600)
        with patch("agent_kit.auth.CREDENTIALS_PATH", creds_file):
            assert get_field("slack", "token") is None


class TestSetField:
    def test_sets_new_field(self, tmp_path):
        creds_file = tmp_path / "creds.yaml"
        creds_file.write_text(yaml.dump({}))
        creds_file.chmod(0o600)
        with (
            patch("agent_kit.auth.CREDENTIALS_PATH", creds_file),
            patch("agent_kit.auth.AGENT_KIT_HOME", tmp_path),
        ):
            set_field("slack", "token", "abc")
        loaded = yaml.safe_load(creds_file.read_text())
        assert loaded["slack"]["token"] == "abc"

    def test_preserves_existing_fields(self, tmp_path):
        creds_file = tmp_path / "creds.yaml"
        creds_file.write_text(yaml.dump({"slack": {"existing": "keep"}}))
        creds_file.chmod(0o600)
        with (
            patch("agent_kit.auth.CREDENTIALS_PATH", creds_file),
            patch("agent_kit.auth.AGENT_KIT_HOME", tmp_path),
        ):
            set_field("slack", "new", "val")
        loaded = yaml.safe_load(creds_file.read_text())
        assert loaded["slack"]["existing"] == "keep"
        assert loaded["slack"]["new"] == "val"


class TestSetFields:
    def test_sets_multiple(self, tmp_path):
        creds_file = tmp_path / "creds.yaml"
        creds_file.write_text(yaml.dump({}))
        creds_file.chmod(0o600)
        with (
            patch("agent_kit.auth.CREDENTIALS_PATH", creds_file),
            patch("agent_kit.auth.AGENT_KIT_HOME", tmp_path),
        ):
            set_fields("jira", {"email": "a@b.com", "token": "xyz"})
        loaded = yaml.safe_load(creds_file.read_text())
        assert loaded["jira"]["email"] == "a@b.com"
        assert loaded["jira"]["token"] == "xyz"
