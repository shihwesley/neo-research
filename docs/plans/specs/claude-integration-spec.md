---
name: claude-integration
phase: 2
sprint: 1
parent: null
depends_on: [mcp-server]
status: draft
created: 2026-02-11
---

# Claude Code Integration

## Overview
The glue that makes Claude Code use the sandbox automatically. MCP config for tool discovery, CLAUDE.md routing rules, and an optional PreToolUse hook for auto-redirecting large file reads.

## Requirements
- [ ] REQ-1: mcp-config.json entry that registers the RLM MCP server with Claude Code
- [ ] REQ-2: CLAUDE.md rules that tell Claude when to prefer rlm.* tools over native tools
- [ ] REQ-3: Routing rules: files >200 lines -> rlm.load, multi-file analysis -> rlm.exec
- [ ] REQ-4: Sub-agents should write results to sandbox variables, not into context

## Acceptance Criteria
- [ ] AC-1: Starting a Claude Code session with mcp-config.json shows rlm.* tools in tool list
- [ ] AC-2: With routing rules, Claude uses rlm.load for large files without explicit prompting
- [ ] AC-3: Multi-step analysis uses rlm.exec to keep intermediate results in sandbox
- [ ] AC-4: Setup instructions in README work on a fresh Claude Code installation

## Technical Approach
mcp-config.json points Claude Code at the MCP server's entry point (srt-wrapped).
Routing rules go in a separate `.claude/` file — does not modify user's existing CLAUDE.md.
No code changes to Claude Code — it's all configuration and prompting.

The routing rules are the critical piece: they tell the agent to reach for rlm.load
instead of Read for large files. Without them, the sandbox exists but the agent ignores it.

## Files
| File | Action | Purpose |
|------|--------|---------|
| claude-integration/mcp-config.json | create | MCP server registration for Claude Code |
| claude-integration/rlm-routing-rules.md | create | Separate .claude/ file with rlm.* routing rules |
| claude-integration/setup.sh | create | Installer script (copies config, installs routing rules) |
| README.md | create | Project overview, three isolation tiers, quick start, tool reference |
| tests/test_integration.py | create | Smoke test: verify rlm.* tools discoverable |

## Tasks
1. Create mcp-config.json with srt-wrapped server entry point and env vars
2. Write rlm routing rules as a separate .claude/ include file
3. Create setup.sh installer (symlinks config, installs routing rules to .claude/)
4. Write README.md with isolation tiers, quick start, tool reference
5. Write smoke test for tool discovery

## Dependencies
- **Needs from mcp-server:** the MCP server to register and point at
- **Provides to:** end user (this is the final integration layer)

## Resolved Questions
- CLAUDE.md: separate file in `.claude/`, not modify user's existing CLAUDE.md
- Auto-redirect hook: deferred to v2 (routing rules in .claude/ cover the core behavior)
- Three-tier isolation docs go in README.md

## Research Spike Updates (2026-02-12)
- **Three-tier isolation docs:** Document the isolation tiers in README:
  Tier 1 (--no-docker): srt-only, ~200ms startup, process-level isolation
  Tier 2 (default): Docker kernel + srt MCP server, ~4s startup
  Tier 3: Docker Sandboxes deployment (future, requires Docker Desktop upgrade)
- **/sandbox compatibility:** rlm.* MCP tools go through MCP permissions, not bash sandbox.
  Native /sandbox and srt don't conflict — they sandbox different processes.
  Document that enabling /sandbox with rlm-sandbox is recommended for defense-in-depth.
- **Docker Sandboxes deployment:** `docker sandbox` not in Docker Desktop 28.0.1.
  Defer as a future deployment target. Document requirements when available.
