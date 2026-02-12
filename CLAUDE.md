# CLAUDE.md

Docker sandbox for executing Python/DSPy code in isolated containers, exposed to Claude via an MCP server.

## Planning

This project uses spec-driven planning. All specs and dependency graph live in `docs/plans/`.

- **Manifest:** `docs/plans/manifest.md` (dependency DAG, phase/sprint map)
- **Specs:** `docs/plans/specs/*.md` (one per component)
- **Progress:** `docs/plans/progress.md`
- **Findings:** `docs/plans/findings.md`

Read the manifest before starting any implementation work.

## Architecture (brief)

```
Claude ↔ MCP Server (host) ↔ Docker Container (FastAPI + IPython kernel)
                 ↕
           DSPy (host-side, talks to Haiku 4.5)
```

DSPy runs on the host inside the MCP server process — no API keys enter the container.

## Conventions

- Container gets no network access and no API keys
- DSPy optimization happens host-side, results passed into sandbox
- Use `dill` for session persistence (save/restore kernel state)

## Context Awareness

Context window management, context-forward.md, and tool path rules are in the global `~/.claude/CLAUDE.md`. Do not duplicate here.
