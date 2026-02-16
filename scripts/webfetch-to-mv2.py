#!/usr/bin/env python3
"""PostToolUse hook: auto-index WebFetch results into .mv2 knowledge store.

Reads tool input from stdin JSON, extracts the URL, re-fetches through
the enhanced fetcher (Accept: text/markdown cascade), and ingests into
the KnowledgeStore.

Exit 0 = allow (always), stdout = feedback to Claude.
"""

import json
import sys
import asyncio
from pathlib import Path

# Add parent so we can import mcp_server modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = data.get("tool_name", "")
    if tool_name != "WebFetch":
        return

    tool_input = data.get("tool_input", {})
    url = tool_input.get("url", "")
    if not url:
        return

    # Skip blocked domains
    from urllib.parse import urlparse
    import re
    host = urlparse(url).hostname or ""
    base_host = re.sub(r"^(www|docs)\.", "", host)
    BLOCKED = {"medium.com", "substack.com"}
    if base_host in BLOCKED:
        return

    # Check freshness -- skip if already indexed recently
    from mcp_server.fetcher import url_to_filepath, is_fresh
    doc_path = url_to_filepath(url)
    if is_fresh(doc_path):
        return

    # Re-fetch through enhanced fetcher
    asyncio.run(_fetch_and_index(url))


async def _fetch_and_index(url: str):
    import httpx
    from mcp_server.fetcher import fetch_url, extract_library_name

    async with httpx.AsyncClient() as client:
        result = await fetch_url(client, url, force=False)

    if result["error"] or not result["content"]:
        return

    # Ingest into knowledge store (standalone -- not inside MCP server process)
    try:
        from mcp_server.knowledge import get_store
        store = get_store()
        store.ingest(
            title=url,
            label=extract_library_name(url),
            text=result["content"],
            metadata=result["meta"] or {},
        )
        source = (result["meta"] or {}).get("markdown_source", "unknown")
        print(f"Auto-indexed {url} into knowledge store (via {source})")
    except Exception:
        # Silent failure -- don't block the agent
        pass


if __name__ == "__main__":
    main()
