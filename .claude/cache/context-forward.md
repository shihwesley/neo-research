## Task: Build rlm-sandbox — MCP-bridged Docker sandbox for Claude Code (RLM pattern)
## Progress: Phase 0 (sandbox-research) COMPLETE. All specs reviewed, decisions resolved. Ready for Phase 1.
## Decisions:
- Hybrid (Docker+srt) as primary architecture
- srt-only as --no-docker lightweight fallback
- --dns 0.0.0.0 replaces --network=none (port mapping needs bridge)
- DSPy runs HOST-SIDE in MCP server (not in container — avoids API key in container)
- SandboxInterpreter implements CodeInterpreter protocol, routes code to container /exec
- llm_query callback: container gets stub that POSTs to host for LLM calls
- MCP Python SDK (MCPServer class) with lifespan hooks for lazy container startup
- Separate .claude/ routing rules file (don't modify user's CLAUDE.md)
- Session ID = hash of working directory (per-project isolation)
- Dedicated /snapshot/save and /snapshot/restore endpoints (not POST /exec with dill)
- stdout + separate stderr in /exec response
- Docker Sandboxes deferred (unavailable in Docker Desktop 28.0.1)
- Three-tier isolation model: srt-only (Tier 1), Docker+srt (Tier 2), Docker Sandboxes (Tier 3)
## Files:
- docs/plans/manifest.md — 6 specs, sandbox-research complete, rest ready
- docs/plans/findings.md — full research + decisions + DSPy host-side update
- docs/plans/progress.md — Phase 0 done, all specs reviewed and ready
- docs/plans/specs/ — all 6 specs updated with review findings
- research/ — prototypes (srt-prototype 15/15, hybrid-prototype 7/7)
## Next: /orchestrate --resume ./docs/plans — execute Phase 1, Sprint 1 (docker-sandbox)
## User's Last Request: Update plan with review findings, move DSPy host-side, resolve all open questions.
