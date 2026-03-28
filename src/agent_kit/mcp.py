"""Generic MCP session management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@asynccontextmanager
async def mcp_session(url: str, headers: dict[str, str]) -> AsyncIterator[ClientSession]:
    """Connect to an MCP server and yield an initialised session."""
    async with streamablehttp_client(url=url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
