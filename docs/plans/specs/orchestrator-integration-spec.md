---
name: orchestrator-integration
phase: 4
sprint: 2
parent: null
depends_on: [doc-fetcher, search-engine]
status: draft
created: 2026-02-12
updated: 2026-02-13
---

# Orchestrator & Planning Integration

## Overview
Wire the memvid knowledge store into existing workflows. /orchestrate Stage 4 (RESEARCH) auto-fetches and indexes docs. /interactive-planning research phases use rlm_search instead of flooding context. Users can manually trigger research via rlm_research. The core value: agents say "use rlm_search" instead of reading full doc files into context.

## Requirements
- [ ] REQ-1: /orchestrate Stage 4 uses rlm_fetch_sitemap + rlm_load_dir to populate knowledge store before agent dispatch
- [ ] REQ-2: /interactive-planning research phases use rlm_search and rlm_ask to query docs without context bloat
- [ ] REQ-3: `rlm_research(topic)` compound tool — resolve docs for a topic, fetch, index, return confirmation
- [ ] REQ-4: Agent prompts include "query docs via rlm_search/rlm_ask, do NOT read full doc files"
- [ ] REQ-5: `rlm_knowledge_status()` — show what's indexed, when, how many chunks per source
- [ ] REQ-6: `rlm_knowledge_clear()` — clear .mv2 index for current project (optional cleanup)
- [ ] REQ-7: Context7 integration — route Context7 results through knowledge store for future rlm_search queries

## Acceptance Criteria
- [ ] AC-1: /orchestrate --resume on a new phase auto-fetches tech docs into knowledge store
- [ ] AC-2: Agent prompts contain "use rlm_search for docs" — verified by reading generated prompts
- [ ] AC-3: `rlm_research("fastapi")` fetches FastAPI docs sitemap, indexes them, returns "Indexed N chunks from M pages"
- [ ] AC-4: `rlm_knowledge_status()` returns table of indexed sources with chunk counts and dates
- [ ] AC-5: After rlm_knowledge_clear(), rlm_search returns empty results
- [ ] AC-6: Context7 fetches get dual-stored (raw + .mv2) for future rlm_search queries
- [ ] AC-7: End-to-end: fetch docs → rlm_search returns relevant chunks → Claude uses them without reading full files

## Technical Approach

### rlm_research(topic) — Compound Tool

One-call research workflow:
1. Look up topic via Context7 (`resolve-library-id`) to find official docs
2. If docs site has sitemap → `rlm_fetch_sitemap(sitemap_url)`
3. If no sitemap → `rlm_fetch` key pages (README, API reference, quickstart)
4. Return summary: "Indexed N chunks from M sources for {topic}. Use rlm_search to query."

### Orchestrator Changes (Stage 4: RESEARCH)

Current flow: fetch docs → write .claude/docs/ cheat sheets → agent reads cheat sheets in context.

New flow: fetch docs → dual-store (raw files + .mv2) → agent prompts say "use rlm_search".

Cheat sheets still created as raw files (TLDR cache fallback for offline/degraded mode).

### Interactive Planning Changes

Research gates in /interactive-planning:
- Before: WebFetch URLs → paste content into findings.md → context bloat
- After: `rlm_fetch(url)` → content stored in .mv2 → `rlm_search` during implementation

### Agent Prompt Template Addition

```
## Knowledge Store Available
Tech docs are indexed in the knowledge store. Query them with:
- rlm_search(query) — hybrid search for relevant doc chunks
- rlm_ask(question, context_only=True) — get context chunks for a question
- rlm_timeline() — browse recently indexed docs

Do NOT read full doc files into context. Use rlm_search instead.
```

### rlm_knowledge_status()

Returns structured summary:
```
Knowledge Store: ~/.rlm-sandbox/knowledge/{project-hash}.mv2
Sources: 89 documents indexed
Total chunks: ~450
Last updated: 2026-02-13 09:10
Sources:
  - docs.memvid.com: 89 pages, 420 chunks
  - local .tech.md: 5 files, 30 chunks
```

## Files
| File | Action | Purpose |
|------|--------|---------|
| mcp_server/research.py | create | rlm_research compound tool, Context7 integration |
| mcp_server/tools.py | modify | Register rlm_research, rlm_knowledge_status, rlm_knowledge_clear |
| .claude/skills/orchestrator/tech-researcher.md | modify | Route Stage 4 through knowledge store |
| .claude/skills/interactive-planning.md | modify | Use rlm_search in research phases |
| tests/test_research.py | create | Integration tests for research workflow |

## Tasks
1. Implement rlm_research(topic) compound tool (Context7 → fetch → index)
2. Implement rlm_knowledge_status() and rlm_knowledge_clear()
3. Modify orchestrator tech-researcher to dual-store and prompt agents with rlm_search
4. Modify interactive-planning to use rlm_fetch + rlm_search in research phases
5. Add Context7 → knowledge store routing
6. Write integration tests (end-to-end: fetch → index → search → context)

## Dependencies
- **Needs from doc-fetcher:** rlm_fetch, rlm_load_dir, rlm_fetch_sitemap tools
- **Needs from search-engine:** rlm_search, rlm_ask, rlm_timeline tools, KnowledgeStore API
- **Provides to:** end user (research workflow that doesn't eat context window)

## Resolved Questions
- Orchestrator still creates raw .claude/docs/ files as TLDR fallback
- Context7 results get dual-stored (raw + .mv2)
- rlm_research accepts a single topic string — batch topics can call it multiple times
- Agent prompts explicitly say "use rlm_search, don't read files"
