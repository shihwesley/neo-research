# Findings & Decisions — Research Pipeline v2

## Goal
Replace agent zoo with single unified research pipeline that turns any topic into agent expertise via structured methodology → acquisition → REPL distillation → expertise artifact.

## Priority
Quality

## Mode
task-based

## Approach
Single agent, phased execution. One agent runs all 5 phases sequentially. No sub-agent spawning, no coordination overhead. Uses existing MCP tools (rlm_exec, rlm_search, rlm_ingest) as building blocks.

## Requirements
1. Structured research methodology — question tree before searching
2. Format-agnostic acquisition — markdown, PDF, JSON, raw; zero context cost
3. REPL-based knowledge distillation — sandbox queries .mv2 → expertise artifact
4. Expertise artifact as output — 3-5K token mental model, saved + loaded
5. Flexible input — topic string, rich prompt, URLs, or any combination
6. Centralized storage — `~/.claude/research/<topic>/`, no scattering

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Single agent replaces 4 | Current zoo (neo-researcher, neo-research, research-sandbox, research-specialist) has overlapping roles. One agent with clear phases eliminates confusion. |
| Centralized at ~/.claude/research/ | Research happens before/during/across projects. Central location prevents scattering. Any project can read the expertise docs. |
| Question tree before searching | Real research starts with structured questions, not blind Google queries. Each branch maps to source types. |
| Distillation via REPL | The missing piece. Sandbox queries .mv2 systematically, returns structured excerpts. Agent sees ~10-15K tokens of targeted results instead of 500K of raw content. |
| Expertise doc = 3-5K tokens | Enough for a working mental model. Not a summary, not a dump. Knowledge store remains for deep-dives. |
| markdown.new cascade for fetching | Markdown is smaller, cleaner, chunks better in .mv2. Fall back to raw/PDF only when markdown unavailable. |

## Research Findings
- (populated during implementation)

## Visual/Browser Findings
- N/A
