"""Session digest CLI command."""

import sys
from pathlib import Path

import click

from agent_kit.config import load_config
from agent_kit.digest.client import DigestClient
from agent_kit.errors import handle_errors


def _get_client(output_dir: str | None = None) -> DigestClient:
    """Construct DigestClient from config."""
    config = load_config()
    sessions_dir = Path("~/.kiro/sessions/cli").expanduser()
    if output_dir:
        out = Path(output_dir)
    else:
        brain_dir = Path(config.get("brain", {}).get("dir", "~/.archie/brain")).expanduser()
        agent = config.get("agent", "archie")
        out = brain_dir / f"_{agent}" / "logs"
    return DigestClient(sessions_dir, out)


@click.command()
@click.option("--session", "session_id", help="Process a specific session by ID")
@click.option("--since", type=int, help="Only process sessions updated after (unix ms)")
@click.option("--output", "output_dir", help="Override output directory")
@handle_errors
def digest(session_id: str | None, since: int | None, output_dir: str | None) -> None:
    """Digest session logs into structured YAML for analysis."""
    client = _get_client(output_dir)

    if session_id:
        path = client.digest_session(session_id)
        print(f"Written: {path}", file=sys.stderr)
        return

    result = client.digest_all(since=since)
    print(
        f"Processed: {result['processed']}, "
        f"Skipped: {result['skipped']}, "
        f"Errors: {result['errors']}",
        file=sys.stderr,
    )
