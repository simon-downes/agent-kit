"""Top-level init command — sets up the brain and persists config."""

import subprocess
from importlib.resources import as_file, files
from pathlib import Path

import click

from agent_kit.config import CONFIG_PATH, load_config, save_config
from agent_kit.errors import handle_errors


def _load_template(name: str) -> str:
    """Load a template file from the package."""
    templates = files("agent_kit").joinpath("brain", "templates", name)
    with as_file(templates) as path:
        return path.read_text()


def _render(template: str, user: str, agent: str) -> str:
    """Substitute placeholders in a template."""
    return template.replace("{{USER}}", user).replace("{{AGENT}}", agent)


@click.command()
@click.option("--user", prompt="User name", default="simon", show_default=True)
@click.option("--agent", prompt="Agent name", default="archie", show_default=True)
@handle_errors
def init(user: str, agent: str) -> None:
    """Initialise the brain and persist config."""
    config = load_config()
    brain_dir = Path(config.get("brain", {}).get("dir", "~/.archie/brain")).expanduser()

    if brain_dir.exists() and any(brain_dir.iterdir()):
        raise ValueError(f"Brain directory already exists and is not empty: {brain_dir}")

    click.echo(f"Initialising brain at {brain_dir}...")

    # Create directories
    dirs = [
        brain_dir / f"_{agent}",
        brain_dir / f"_{agent}" / "memory",
        brain_dir / "_inbox",
        brain_dir / user,
        brain_dir / "people",
        brain_dir / "projects",
        brain_dir / "knowledge",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        click.echo(f"  Created {d.relative_to(brain_dir)}/")

    # Write templated files
    brain_md = _render(_load_template("BRAIN.md"), user, agent)
    (brain_dir / "BRAIN.md").write_text(brain_md)
    click.echo("  Created BRAIN.md")

    profile_md = _render(_load_template("profile.md"), user, agent)
    (brain_dir / user / "profile.md").write_text(profile_md)
    click.echo(f"  Created {user}/profile.md")

    # Empty operational files
    (brain_dir / f"_{agent}" / "memory.md").write_text("")
    click.echo(f"  Created _{agent}/memory.md")

    (brain_dir / f"_{agent}" / "signals.yaml").write_text("")
    click.echo(f"  Created _{agent}/signals.yaml")

    # Initialise git repo
    result = subprocess.run(
        ["git", "init"],
        cwd=brain_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        click.echo("  Initialised git repo")
    else:
        click.echo(f"  Warning: git init failed: {result.stderr.strip()}")

    # Persist user/agent in config
    config["user"] = user
    config["agent"] = agent
    save_config(config)
    click.echo(f"  Saved user={user}, agent={agent} to {CONFIG_PATH}")

    click.echo("Done.")
