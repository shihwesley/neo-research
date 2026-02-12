"""MCP server bridging Claude Code to the Docker sandbox."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from mcp.server.fastmcp import FastMCP

from mcp_server.docker_manager import DockerManager
from mcp_server.session import SessionManager
from mcp_server.tools import register_tools

log = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Shared resources available to all tools via lifespan context."""

    manager: DockerManager
    http: httpx.AsyncClient


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Create shared resources on startup, clean up on shutdown."""
    manager = DockerManager()
    client = httpx.AsyncClient()
    session = SessionManager()
    try:
        await manager.ensure_running()
        await session.restore()
        session.start_auto_save()
        SessionManager.cleanup_expired()
        yield AppContext(manager=manager, http=client)
    finally:
        # Save before tearing down the container
        try:
            await session.save()
        except Exception:
            log.exception("Final session save failed")
        await session.stop_auto_save()
        await client.aclose()
        await manager.stop()


mcp = FastMCP("rlm-sandbox", lifespan=lifespan)
register_tools(mcp)


if __name__ == "__main__":
    mcp.run(transport="stdio")
