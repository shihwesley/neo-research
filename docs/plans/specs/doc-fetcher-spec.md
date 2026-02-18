---
name: doc-fetcher
phase: 4
sprint: 1
parent: null
depends_on: [search-spike]
status: draft
created: 2026-02-12
updated: 2026-02-13
---

# Document Fetcher

## Overview
Fetching layer that pulls documentation from web URLs, local files, and sitemaps into dual storage: raw markdown files in `.claude/docs/` (human-browsable, TLDR cache compatible) AND indexed into the project's `.mv2` knowledge store. Handles blocked sites, prefers .md sources, tracks freshness metadata, supports bulk ingestion.

## Requirements
- [ ] REQ-1: `rlm_fetch(url)` MCP tool — fetch URL content, store as raw .md file AND ingest into .mv2
- [ ] REQ-2: Smart URL resolution — try .md variant first (Mintlify/Fumadocs convention), fall back to HTML→markdown
- [ ] REQ-3: `rlm_load_dir(glob_pattern)` MCP tool — bulk-load local files as raw + .mv2 ingestion
- [ ] REQ-4: `rlm_fetch_sitemap(sitemap_url)` MCP tool — parse sitemap.xml, fetch all pages, bulk ingest
- [ ] REQ-5: Source metadata on each .mv2 frame — URL, fetch date, content hash, file size
- [ ] REQ-6: Cache freshness — skip re-fetch if raw file exists and is <7 days old, force refresh option
- [ ] REQ-7: Graceful degradation — blocked/unreachable URLs return clear error, one attempt only
- [ ] REQ-8: Dual storage — raw .md to `.claude/docs/{library}/` + `mem.put()` into .mv2

## Acceptance Criteria
- [ ] AC-1: `rlm_fetch("https://docs.example.com/api")` creates raw .md file AND indexes into .mv2, returns confirmation (not content)
- [ ] AC-2: For a URL with .md variant, fetcher uses the .md version (verified by checking raw file is markdown, not HTML)
- [ ] AC-3: `rlm_load_dir("**/*.tech.md")` loads 20+ files into both raw storage and .mv2, returns count
- [ ] AC-4: `rlm_fetch_sitemap("https://docs.memvid.com/sitemap.xml")` fetches all pages, indexes them, returns summary
- [ ] AC-5: Re-fetching a cached URL within 7 days returns "already cached" without re-downloading
- [ ] AC-6: Fetching a blocked URL returns error within 5 seconds, suggests paste
- [ ] AC-7: All .mv2 frames have source attribution metadata (URL or file path, fetch timestamp, content hash)

## Technical Approach

### Dual Storage Architecture

```
rlm_fetch(url)
  ├── Raw file → .claude/docs/{library}/{path}.md  (human-readable, TLDR cache)
  └── mem.put() → ~/.neo-research/knowledge/{project}.mv2  (search index)
```

The raw files let TLDR read-enforcer hooks work (93% token savings on reads). The .mv2 gives semantic search without reading files into context at all.

### URL Resolution Strategy
1. Parse URL → extract library name from domain (e.g., `docs.memvid.com` → `memvid`)
2. Try `{url}.md` first (Mintlify convention — many modern doc sites serve raw markdown)
3. If .md returns non-markdown (HTML), fall back to fetching original URL
4. Convert HTML → markdown via html2text
5. If fetch fails (403, timeout, connection refused) → return error immediately, one attempt only

### Sitemap Fetcher
- Parse XML sitemap → extract all `<loc>` URLs
- Apply .md variant detection to each
- Batch download with rate limiting (200ms between requests)
- Store each page as raw file + .mv2 frame
- Return summary: N pages fetched, M failed, total size

### Freshness Tracking
Each raw file gets a sidecar `.meta.json`:
```json
{"url": "...", "fetched_at": "2026-02-13T...", "content_hash": "sha256:...", "size_bytes": 12345}
```
On re-fetch: check if meta exists and is <7 days old. If so, skip unless `force=True`.

### Bulk Local Loading
- Resolve glob pattern against project root
- Each file read as markdown
- Store as both raw file (if not already in .claude/docs/) and .mv2 frame
- .chronicler/*.tech.md files are first-class citizens (already markdown)

## Files
| File | Action | Purpose |
|------|--------|---------|
| mcp_server/fetcher.py | create | URL fetching, .md detection, HTML→md, sitemap parsing, freshness |
| mcp_server/tools.py | modify | Register rlm_fetch, rlm_load_dir, rlm_fetch_sitemap tools |
| tests/test_fetcher.py | create | URL resolution, blocked sites, freshness, bulk loading, sitemap |

## Tasks
1. Implement URL fetching with .md variant detection and HTML→markdown fallback
2. Implement sitemap parser and batch fetcher
3. Implement dual storage (raw file + .mv2 ingestion)
4. Implement bulk local file loading with glob patterns
5. Add source metadata tracking and freshness checking
6. Register rlm_fetch, rlm_load_dir, rlm_fetch_sitemap as MCP tools
7. Write tests for all fetching scenarios

## Dependencies
- **Needs from search-spike:** hosting decision (host-side confirmed)
- **Needs from search-engine:** KnowledgeStore.ingest() API for .mv2 ingestion
- **Provides to orchestrator-integration:** rlm_fetch, rlm_load_dir, rlm_fetch_sitemap tools

## Resolved Questions
- Fetcher runs host-side (needs network, container has none)
- One fetch attempt only — no retries, no workarounds for blocked sites
- HTML→markdown via html2text (lighter than markdownify)
- Dual storage: raw files for TLDR cache + .mv2 for semantic search
- Sitemap support added — this is how we just fetched the memvid docs
