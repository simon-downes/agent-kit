"""MCP client connection management."""

from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from notion.auth import NOTION_MCP_URL


async def connect_to_notion(access_token: str) -> tuple[ClientSession, Any, Any]:
    """Connect to Notion MCP server.

    Returns (session, session_context, streams_context) tuple.
    Caller is responsible for cleanup via __aexit__.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    streams_context = streamablehttp_client(url=NOTION_MCP_URL, headers=headers)

    try:
        read, write, _ = await streams_context.__aenter__()

        session_context = ClientSession(read, write)
        session = await session_context.__aenter__()
        await session.initialize()

        return session, session_context, streams_context
    except Exception:
        await streams_context.__aexit__(None, None, None)
        raise
