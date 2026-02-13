#!/usr/bin/env bash
# PostToolUse hook: when Context7 query-docs returns content,
# also ingest it into the rlm-sandbox knowledge store via rlm_ingest.
#
# This hook reads the tool result from stdin (JSON) and checks if it's
# a Context7 query-docs call. If so, it extracts the content and calls
# rlm_ingest to dual-store it.
#
# Hook contract: exit 0 = allow, exit 2 = block, stdout = feedback to Claude.

set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || echo "")

# Only intercept Context7 query-docs results
if [[ "$TOOL_NAME" != "mcp__context7__query-docs" ]]; then
    exit 0
fi

# Extract the library name and content from the tool result
LIBRARY=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
params = data.get('tool_params', {})
lib_id = params.get('libraryId', 'unknown')
# Extract library name from ID (format: /org/repo)
name = lib_id.strip('/').split('/')[-1] if '/' in lib_id else lib_id
print(name)
" 2>/dev/null || echo "unknown")

# Signal to Claude that this content should also be ingested
echo "Context7 docs for '$LIBRARY' fetched. Consider running rlm_ingest to index this content for future rlm_search queries."

exit 0
