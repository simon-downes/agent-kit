"""Tests for agent_kit.config."""

from unittest.mock import patch

import pytest
import yaml

from agent_kit.config import DEFAULT_CONFIG, _deep_merge, load_config, save_config


class TestDeepMerge:
    def test_flat_override(self):
        assert _deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_adds_new_keys(self):
        assert _deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"y": 3, "z": 4}}
        assert _deep_merge(base, override) == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_override_dict_with_scalar(self):
        assert _deep_merge({"a": {"x": 1}}, {"a": "flat"}) == {"a": "flat"}

    def test_override_scalar_with_dict(self):
        assert _deep_merge({"a": "flat"}, {"a": {"x": 1}}) == {"a": {"x": 1}}

    def test_empty_override(self):
        base = {"a": 1}
        assert _deep_merge(base, {}) == {"a": 1}

    def test_does_not_mutate_base(self):
        base = {"a": {"x": 1}}
        _deep_merge(base, {"a": {"x": 2}})
        assert base == {"a": {"x": 1}}


class TestLoadConfig:
    def test_returns_defaults_when_file_missing(self, tmp_path):
        missing = tmp_path / "nope.yaml"
        with patch("agent_kit.config.CONFIG_PATH", missing):
            config = load_config()
        assert config == DEFAULT_CONFIG

    def test_merges_overrides(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump({"project_dir": "/custom"}))
        with patch("agent_kit.config.CONFIG_PATH", cfg_file):
            config = load_config()
        assert config["project_dir"] == "/custom"
        # defaults still present
        assert "auth" in config

    def test_nested_override_preserves_siblings(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump({"slack": {"read": {"enabled": False}}}))
        with patch("agent_kit.config.CONFIG_PATH", cfg_file):
            config = load_config()
        assert config["slack"]["read"]["enabled"] is False
        assert config["slack"]["write"]["enabled"] is True

    def test_exits_on_malformed_yaml(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("not: valid: yaml: [")
        with patch("agent_kit.config.CONFIG_PATH", cfg_file):
            with pytest.raises(SystemExit, match="1"):
                load_config()

    def test_exits_on_non_dict_yaml(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("- a list\n- not a dict\n")
        with patch("agent_kit.config.CONFIG_PATH", cfg_file):
            with pytest.raises(SystemExit, match="1"):
                load_config()

    def test_empty_file_returns_defaults(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")
        with patch("agent_kit.config.CONFIG_PATH", cfg_file):
            config = load_config()
        assert config == DEFAULT_CONFIG


class TestSaveConfig:
    def test_creates_file(self, tmp_path):
        cfg_file = tmp_path / "sub" / "config.yaml"
        with patch("agent_kit.config.CONFIG_PATH", cfg_file):
            save_config({"project_dir": "/test"})
        assert cfg_file.exists()
        loaded = yaml.safe_load(cfg_file.read_text())
        assert loaded["project_dir"] == "/test"
