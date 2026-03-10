"""Output formatting for Notion content."""

import json
from typing import Any

from rich.console import Console
from rich.markdown import Markdown


def extract_decoded_data(data: list[Any]) -> list[Any]:
    """Extract decoded data from MCP response."""
    decoded = []
    for item in data:
        if isinstance(item, dict):
            text_content = item.get("text", "")

            # Try to parse as JSON if it looks like JSON
            if text_content.startswith("{"):
                try:
                    parsed = json.loads(text_content)
                    decoded.append(parsed)
                    continue
                except json.JSONDecodeError:
                    pass

            if text_content:
                decoded.append(text_content)

    return decoded


def format_json(data: list[Any]) -> str:
    """Format decoded data as JSON."""
    decoded = extract_decoded_data(data)
    return json.dumps(decoded, indent=2)


def format_markdown_raw(data: list[Any]) -> str:
    """Extract and format raw text from MCP response."""
    parts = []
    for item in data:
        if isinstance(item, dict):
            text_content = item.get("text", "")

            # Try to parse as JSON if it looks like JSON
            if text_content.startswith("{"):
                try:
                    parsed = json.loads(text_content)
                    # Extract the nested text field
                    if "text" in parsed:
                        text_content = parsed["text"]
                except json.JSONDecodeError:
                    pass

            if text_content:
                parts.append(text_content)

    return "\n\n".join(parts)


def format_markdown_terminal(data: list[Any], console: Console) -> None:
    """Render markdown to terminal using rich."""
    markdown_text = format_markdown_raw(data)
    if markdown_text:
        md = Markdown(markdown_text)
        console.print(md)
