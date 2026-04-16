"""Notion MCP client — tool calls, response parsing, scope checks."""

import json
import re
from typing import Any

from mcp import ClientSession

from agent_kit.errors import ConfigError, ScopeError

NOTION_MCP_URL = "https://mcp.notion.com/mcp"

_ANCESTOR_RE = re.compile(r'<(?:parent-page|ancestor-\d+-page)\s+url="[^"]*?([a-f0-9]{32})"')


def require_read(config: dict) -> None:
    """Raise ConfigError if read operations are disabled."""
    if not config.get("notion", {}).get("read", {}).get("enabled", True):
        raise ConfigError("Notion read operations are disabled in config")


def require_write(config: dict) -> None:
    """Raise ConfigError if write operations are disabled."""
    if not config.get("notion", {}).get("write", {}).get("enabled", False):
        raise ConfigError("Notion write operations are disabled in config")


def _extract_ancestor_ids(text: str) -> list[str]:
    """Extract ancestor page IDs from MCP response text."""
    return _ANCESTOR_RE.findall(text)


def _in_scope(scope: dict, resource_id: str, text: str) -> bool:
    """Check if resource or any ancestor is in scope."""
    pages = scope.get("pages", [])
    databases = scope.get("databases", [])
    if not pages and not databases:
        return True
    if resource_id in pages or resource_id in databases:
        return True
    for ancestor_id in _extract_ancestor_ids(text):
        if ancestor_id in pages or ancestor_id in databases:
            return True
    return False


def check_read_scope(config: dict, resource_id: str, text: str) -> None:
    """Raise ScopeError if resource is not in read scope."""
    scope = config.get("notion", {}).get("read", {}).get("scope", {})
    if not _in_scope(scope, resource_id, text):
        raise ScopeError(f"{resource_id} is not in configured read scope")


def check_write_scope(config: dict, resource_id: str, text: str) -> None:
    """Raise ScopeError if resource is not in write scope."""
    scope = config.get("notion", {}).get("write", {}).get("scope", {})
    if not _in_scope(scope, resource_id, text):
        raise ScopeError(f"{resource_id} is not in configured write scope")


def extract_id(id_or_url: str) -> str:
    """Extract a Notion ID from a URL or return as-is."""
    if "notion.so" in id_or_url or "notion.site" in id_or_url:
        part = id_or_url.rstrip("/").split("?")[0].split("#")[0].split("-")[-1]
        return part
    return id_or_url


def _parse_content(result: Any) -> list[dict[str, Any]]:
    """Parse MCP tool result into a list of content dicts."""
    return [c.model_dump() for c in result.content]


def _extract_text(content: list[dict[str, Any]]) -> str:
    """Extract text from MCP content blocks."""
    parts = []
    for item in content:
        text = item.get("text", "")
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _try_parse_json(text: str) -> Any:
    """Try to parse text as JSON, return original string on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


async def _fetch_raw(session: ClientSession, resource_id: str) -> tuple[str, Any]:
    """Fetch a resource and return (raw_text, parsed_result).

    raw_text is the inner text content (containing ancestor-path XML),
    suitable for scope checking.
    """
    result = await session.call_tool("notion-fetch", {"id": resource_id})
    content = _parse_content(result)
    text = _extract_text(content)
    parsed = _try_parse_json(text)
    inner_text = parsed.get("text", text) if isinstance(parsed, dict) else text
    return inner_text, parsed


async def fetch_page(
    session: ClientSession, page_id: str, *, properties: bool = False
) -> tuple[str, dict[str, Any]]:
    """Fetch a Notion page. Returns (raw_text, parsed_dict) for scope checking."""
    text, parsed = await _fetch_raw(session, page_id)
    if isinstance(parsed, dict):
        if not properties:
            parsed.pop("properties", None)
        return text, parsed
    return text, {"content": parsed}


async def search(
    session: ClientSession,
    query: str,
    *,
    limit: int = 10,
    filter_type: str | None = None,
) -> list[dict[str, Any]]:
    """Search the Notion workspace. Unrestricted by scope."""
    args: dict[str, Any] = {"query": query, "filters": {}}
    if filter_type:
        args["filters"] = {"type": filter_type}
    result = await session.call_tool("notion-search", args)
    content = _parse_content(result)
    text = _extract_text(content)
    parsed = _try_parse_json(text)

    results: list[dict[str, Any]] = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict) and "results" in item:
                results.extend(item["results"])
            else:
                results.append(item)
    elif isinstance(parsed, dict) and "results" in parsed:
        results = parsed["results"]
    else:
        results = [parsed] if parsed else []

    return results[:limit]


async def fetch_database(session: ClientSession, db_id: str) -> tuple[str, dict[str, Any]]:
    """Fetch database schema. Returns (raw_text, parsed_dict) for scope checking."""
    text, parsed = await _fetch_raw(session, db_id)
    if isinstance(parsed, dict):
        return text, parsed
    return text, {"content": parsed}


async def fetch_comments(
    session: ClientSession, page_id: str, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Fetch comments on a page."""
    result = await session.call_tool("notion-get-comments", {"page_id": page_id})
    content = _parse_content(result)
    text = _extract_text(content)
    parsed = _try_parse_json(text)
    results = parsed if isinstance(parsed, list) else [parsed]
    if limit:
        results = results[:limit]
    return results


async def query_database(
    session: ClientSession,
    db_id: str,
    *,
    view_name: str | None = None,
    filters: list[tuple[str, str, str]] | None = None,
    sort_key: str | None = None,
    sort_reverse: bool = False,
    columns: list[str] | None = None,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Query database rows via a view, with optional post-processing.

    Returns (rows, raw_text) — raw_text is for scope checking.
    """
    text, _ = await _fetch_raw(session, db_id)

    view_url = _find_view_url(text, view_name)
    if not view_url:
        available = list_view_names(text)
        msg = f"No view found for database {db_id}"
        if available:
            msg += f". Available views: {', '.join(available)}"
        raise ValueError(msg)

    result = await session.call_tool("notion-query-database-view", {"view_url": view_url})
    content = _parse_content(result)
    row_text = _extract_text(content)
    parsed = _try_parse_json(row_text)

    rows: list[dict[str, Any]] = []
    if isinstance(parsed, dict) and "results" in parsed:
        rows = parsed["results"]
    elif isinstance(parsed, list):
        rows = parsed
    else:
        rows = [parsed] if parsed else []

    if filters:
        rows = _apply_filters(rows, filters)
    if sort_key:
        rows = sorted(rows, key=lambda r: str(r.get(sort_key, "")), reverse=sort_reverse)
    if columns:
        rows = [{k: r.get(k) for k in columns if k in r} for r in rows]
    if limit:
        rows = rows[:limit]

    return rows, text


def _find_view_url(text: str, view_name: str | None) -> str | None:
    """Find a view URL from database fetch response text."""
    view_pattern = re.compile(
        r'<view\s+url="[{]*(view://[^}"]+)[}]*">\s*(\{.*?\})\s*</view>',
        re.DOTALL,
    )
    for match in view_pattern.finditer(text):
        url = match.group(1)
        try:
            info = json.loads(match.group(2))
            name = info.get("name", "")
        except json.JSONDecodeError:
            name = ""
        if view_name is None:
            return url
        if name.lower() == view_name.lower():
            return url
    return None


def list_view_names(text: str) -> list[str]:
    """Extract available view names from database fetch response."""
    names = []
    view_pattern = re.compile(r'<view\s+url="[^"]*">\s*(\{.*?\})\s*</view>', re.DOTALL)
    for match in view_pattern.finditer(text):
        try:
            info = json.loads(match.group(1))
            name = info.get("name", "")
            if name:
                names.append(name)
        except json.JSONDecodeError:
            pass
    return names


def _apply_filters(
    rows: list[dict[str, Any]], filters: list[tuple[str, str, str]]
) -> list[dict[str, Any]]:
    """Apply post-processing filters. Each filter is (key, op, value)."""
    result = []
    for row in rows:
        match = True
        for key, op, value in filters:
            row_val = str(row.get(key, ""))
            if op == "=" and row_val != value:
                match = False
            elif op == "!=" and row_val == value:
                match = False
            elif op == "contains" and value.lower() not in row_val.lower():
                match = False
            if not match:
                break
        if match:
            result.append(row)
    return result


async def create_page(
    session: ClientSession,
    parent_id: str,
    *,
    title: str | None = None,
    properties: dict[str, str] | None = None,
    content: str | None = None,
) -> dict[str, Any]:
    """Create a new Notion page."""
    page_def: dict[str, Any] = {}
    props = dict(properties) if properties else {}
    if title:
        props["title"] = title
    if props:
        page_def["properties"] = props
    if content:
        page_def["content"] = content

    args: dict[str, Any] = {
        "parent": {"page_id": parent_id},
        "pages": [page_def],
    }

    result = await session.call_tool("notion-create-pages", args)
    content_blocks = _parse_content(result)
    text = _extract_text(content_blocks)
    parsed = _try_parse_json(text)
    return parsed if isinstance(parsed, dict) else {"content": parsed}


async def update_page(
    session: ClientSession,
    page_id: str,
    *,
    properties: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Update a Notion page's properties."""
    args: dict[str, Any] = {
        "page_id": page_id,
        "command": "update_properties",
        "properties": properties or {},
    }

    result = await session.call_tool("notion-update-page", args)
    content_blocks = _parse_content(result)
    text = _extract_text(content_blocks)
    parsed = _try_parse_json(text)
    return parsed if isinstance(parsed, dict) else {"content": parsed}


async def create_comment(
    session: ClientSession,
    page_id: str,
    *,
    message: str,
) -> dict[str, Any]:
    """Add a comment to a Notion page."""
    result = await session.call_tool(
        "notion-create-comment",
        {
            "page_id": page_id,
            "rich_text": [{"type": "text", "text": {"content": message}}],
        },
    )
    content_blocks = _parse_content(result)
    text = _extract_text(content_blocks)
    parsed = _try_parse_json(text)
    return parsed if isinstance(parsed, dict) else {"content": parsed}
