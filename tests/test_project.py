"""Tests for agent_kit.project."""

from unittest.mock import patch

from agent_kit.project import _parse_remote, _resolve_project_config, resolve_project


class TestParseRemote:
    def test_ssh(self):
        org, repo = _parse_remote("git@github.com:my-org/my-repo.git")
        assert org == "my-org"
        assert repo == "my-repo"

    def test_https(self):
        org, repo = _parse_remote("https://github.com/my-org/my-repo.git")
        assert org == "my-org"
        assert repo == "my-repo"

    def test_no_suffix(self):
        org, repo = _parse_remote("https://github.com/my-org/my-repo")
        assert org == "my-org"
        assert repo == "my-repo"

    def test_trailing_slash(self):
        org, repo = _parse_remote("https://github.com/my-org/my-repo/")
        assert org == "my-org"
        assert repo == "my-repo"


class TestResolveProjectConfig:
    def test_empty_config(self):
        result = _resolve_project_config("my-org", "my-repo", {})
        assert result == {}

    def test_defaults_only(self):
        config = {"defaults": {"issues": None, "slack": None}}
        result = _resolve_project_config("my-org", "my-repo", config)
        assert result == {"issues": None, "slack": None}

    def test_org_override(self):
        config = {
            "defaults": {"issues": None, "slack": None},
            "my-org": {"issues": {"provider": "linear", "project": "PLAT"}},
        }
        result = _resolve_project_config("my-org", "my-repo", config)
        assert result["issues"] == {"provider": "linear", "project": "PLAT"}
        assert result["slack"] is None

    def test_exact_repo_override(self):
        config = {
            "my-org": {"issues": {"provider": "linear", "project": "PLAT"}},
            "my-org/my-repo": {"issues": {"provider": "github"}},
        }
        result = _resolve_project_config("my-org", "my-repo", config)
        assert result["issues"] == {"provider": "github"}

    def test_glob_match(self):
        config = {
            "defaults": {"issues": None},
            "my-org/infra-*": {"issues": {"provider": "linear", "project": "INFRA"}},
        }
        result = _resolve_project_config("my-org", "infra-vpc", config)
        assert result["issues"] == {"provider": "linear", "project": "INFRA"}

    def test_glob_no_match(self):
        config = {
            "defaults": {"issues": None},
            "my-org/infra-*": {"issues": {"provider": "linear", "project": "INFRA"}},
        }
        result = _resolve_project_config("my-org", "api-service", config)
        assert result["issues"] is None

    def test_exact_beats_glob(self):
        config = {
            "my-org/infra-*": {"issues": {"provider": "linear", "project": "INFRA"}},
            "my-org/infra-special": {"issues": {"provider": "github"}},
        }
        result = _resolve_project_config("my-org", "infra-special", config)
        assert result["issues"] == {"provider": "github"}

    def test_no_org(self):
        config = {
            "defaults": {"issues": None, "slack": "#general"},
            "my-org": {"issues": {"provider": "linear", "project": "PLAT"}},
        }
        result = _resolve_project_config(None, "my-repo", config)
        assert result == {"issues": None, "slack": "#general"}


class TestResolveProject:
    def test_project_dir_match(self, tmp_path):
        project_dir = tmp_path / "dev"
        cwd = project_dir / "archie" / "src"
        cwd.mkdir(parents=True)
        config = {"project_dir": str(project_dir)}
        with (
            patch("agent_kit.project.Path.cwd", return_value=cwd),
            patch("agent_kit.project._get_remote", return_value=None),
            patch("agent_kit.project._load_projects_config", return_value={}),
        ):
            result = resolve_project(config)
        assert result["name"] == "archie"
        assert result["org"] is None
        assert result["source"] == "local"

    def test_with_remote(self, tmp_path):
        project_dir = tmp_path / "dev"
        cwd = project_dir / "my-repo"
        cwd.mkdir(parents=True)
        config = {"project_dir": str(project_dir)}
        with (
            patch("agent_kit.project.Path.cwd", return_value=cwd),
            patch(
                "agent_kit.project._get_remote",
                return_value="git@github.com:my-org/my-repo.git",
            ),
            patch("agent_kit.project._load_projects_config", return_value={}),
        ):
            result = resolve_project(config)
        assert result["name"] == "my-repo"
        assert result["org"] == "my-org"
        assert result["source"] == "git@github.com:my-org/my-repo.git"

    def test_config_resolved(self, tmp_path):
        project_dir = tmp_path / "dev"
        cwd = project_dir / "my-repo"
        cwd.mkdir(parents=True)
        config = {"project_dir": str(project_dir)}
        projects_config = {"my-org": {"issues": {"provider": "linear", "project": "PLAT"}}}
        with (
            patch("agent_kit.project.Path.cwd", return_value=cwd),
            patch(
                "agent_kit.project._get_remote",
                return_value="git@github.com:my-org/my-repo.git",
            ),
            patch("agent_kit.project._load_projects_config", return_value=projects_config),
        ):
            result = resolve_project(config)
        assert result["issues"] == {"provider": "linear", "project": "PLAT"}

    def test_no_remote_no_config(self, tmp_path):
        project_dir = tmp_path / "dev"
        cwd = project_dir / "new-project"
        cwd.mkdir(parents=True)
        config = {"project_dir": str(project_dir)}
        with (
            patch("agent_kit.project.Path.cwd", return_value=cwd),
            patch("agent_kit.project._get_remote", return_value=None),
            patch("agent_kit.project._load_projects_config", return_value={}),
        ):
            result = resolve_project(config)
        assert result["name"] == "new-project"
        assert result["org"] is None
        assert result["issues"] is None
        assert result["slack"] is None
