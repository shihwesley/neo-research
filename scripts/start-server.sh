#!/usr/bin/env bash
set -euo pipefail

# Start the rlm-sandbox MCP server.
# Called by Claude Code via .mcp.json — communicates over stdio.

PLUGIN_ROOT="${RLM_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
VENV_DIR="$PLUGIN_ROOT/.venv"

# Auto-setup on first run
if [ ! -d "$VENV_DIR" ]; then
    "$PLUGIN_ROOT/scripts/setup.sh" >&2
fi

exec "$VENV_DIR/bin/python" -m mcp_server.server
