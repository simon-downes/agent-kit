"""Tests for output formatting."""

from agent_kit.notion.output import format_json, format_markdown_raw


def test_format_json():
    """Test JSON formatting."""
    data = [{"type": "text", "text": "Hello"}]
    result = format_json(data)
    assert "Hello" in result


def test_format_json_with_nested():
    """Test JSON formatting with nested JSON."""
    import json

    nested = {"metadata": {"type": "page"}, "text": "Content"}
    data = [{"type": "text", "text": json.dumps(nested)}]
    result = format_json(data)
    parsed = json.loads(result)
    assert parsed[0]["metadata"]["type"] == "page"
    assert parsed[0]["text"] == "Content"


def test_format_markdown_raw():
    """Test raw markdown extraction."""
    data = [
        {"type": "text", "text": "# Title"},
        {"type": "text", "text": "Content here"},
    ]
    result = format_markdown_raw(data)
    assert "# Title" in result
    assert "Content here" in result
    assert "\n\n" in result


def test_format_markdown_raw_with_text_field():
    """Test raw markdown extraction with direct text field."""
    data = [
        {"text": "# Title\nSome content", "metadata": {"type": "page"}},
    ]
    result = format_markdown_raw(data)
    assert "# Title" in result
    assert "Some content" in result


def test_format_markdown_raw_with_nested_json():
    """Test raw markdown extraction with nested JSON in text field."""
    import json

    nested_data = {"text": "# Actual Markdown\nContent here", "metadata": {}}
    data = [
        {"type": "text", "text": json.dumps(nested_data)},
    ]
    result = format_markdown_raw(data)
    assert "# Actual Markdown" in result
    assert "Content here" in result


def test_format_markdown_raw_empty():
    """Test raw markdown with empty data."""
    data = []
    result = format_markdown_raw(data)
    assert result == ""


def test_format_markdown_raw_non_text():
    """Test raw markdown ignores non-text items."""
    data = [
        {"type": "image", "url": "https://example.com/image.png"},
        {"type": "text", "text": "Some text"},
    ]
    result = format_markdown_raw(data)
    assert "Some text" in result
    assert "image.png" not in result
