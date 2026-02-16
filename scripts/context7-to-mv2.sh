#!/usr/bin/env bash
# PostToolUse hook: ingest Context7 query-docs content into .mv2 knowledge store.
#
# Reads tool result from stdin JSON, extracts library name and content,
# calls Python to ingest into KnowledgeStore.
#
# Exit 0 = allow (always), stdout = feedback to Claude.

set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || echo "")

if [[ "$TOOL_NAME" != "mcp__context7__query-docs" ]]; then
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Use the project venv python (has all dependencies)
VENV_PYTHON="${SCRIPT_DIR}/../.venv/bin/python3"
if [[ ! -x "$VENV_PYTHON" ]]; then
    VENV_PYTHON="python3"
fi

echo "$INPUT" | "$VENV_PYTHON" -c "
import sys, json
sys.path.insert(0, '${SCRIPT_DIR}/..')

data = json.load(sys.stdin)
params = data.get('tool_params', {})
result = data.get('tool_result', '')

lib_id = params.get('libraryId', 'unknown')
name = lib_id.strip('/').split('/')[-1] if '/' in lib_id else lib_id

if not result or len(str(result)) < 50:
    sys.exit(0)

try:
    from mcp_server.knowledge import get_store
    store = get_store()
    content = result if isinstance(result, str) else str(result)
    store.ingest(
        title=f'context7:{name}',
        label=f'context7-{name}',
        text=content,
        metadata={'source': 'context7', 'library': name},
    )
    print(f'Context7 docs for \"{name}\" indexed into knowledge store.')
except Exception as e:
    print(f'Context7 indexing skipped: {e}')
" 2>/dev/null || true

exit 0
