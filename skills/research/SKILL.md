---
name: research
description: Research a library or framework — fetches docs, indexes into knowledge store, confirms what's searchable. Use when you need to learn about a technology before implementation.
---

# Research: $ARGUMENTS

Research the topic "$ARGUMENTS" using the rlm-sandbox knowledge store. This skill fetches documentation, indexes it for hybrid search, and verifies it's queryable — so you and the user can search docs without reading entire files into context.

## When This Skill Triggers

Use this when the user:
- Says "research X", "look up X docs", "learn about X before we start"
- Asks to index documentation for a library or framework
- Needs to understand an unfamiliar dependency before implementation
- Wants to populate the knowledge store for later `rlm_search` queries

## Step 1: Parse the Topic

The `$ARGUMENTS` string is the topic to research. It's usually a library or framework name, but could also be a broader concept.

Common inputs:
- Library names: "fastapi", "dspy", "pydantic", "numpy"
- Framework names: "django", "flask", "langchain"
- Compound topics: "fastapi dependency injection", "pytorch dataloaders"

For compound topics, extract the library name for the fetch step and keep the full phrase for verification searches. For example:
- "fastapi dependency injection" → fetch "fastapi", then verify with `rlm_search("dependency injection")`
- "numpy linear algebra" → fetch "numpy", then verify with `rlm_search("linear algebra numpy")`

If the topic is ambiguous (e.g. "auth" or "testing"), ask the user which library or framework they mean before proceeding.

## Step 2: Check What's Already Indexed

Call `rlm_knowledge_status()` to see if this topic's docs are already in the store.

```
rlm_knowledge_status()
```

**If the topic is already indexed** (the library appears in the sources list):
- Skip to Step 4 (verification) to confirm it's searchable.
- Tell the user: "Docs for {topic} are already indexed ({N} pages). Verifying searchability..."
- Don't re-fetch unless the user explicitly asks to refresh.

**If the topic is not indexed**, continue to Step 3.

## Step 3: Fetch Documentation

### 3a: Try `rlm_research` first (recommended)

This is the one-call approach. It checks known doc URL mappings for 25+ common libraries, tries sitemap.xml patterns, and fetches + indexes pages automatically.

```
rlm_research("$ARGUMENTS")
```

The tool returns one of:
- **Success**: "Indexed {N} pages for '{topic}'. {M} failed. Use rlm_search to query."
- **Failure**: "Could not fetch docs for '{topic}'. Tried {N} URL patterns, all failed."

**If successful**, jump to Step 4 (verification).

**If it failed**, continue to 3b.

### 3b: Manual URL discovery

When `rlm_research` can't find the docs automatically, locate them manually:

1. Use `WebSearch` to find the official documentation:
   ```
   WebSearch("{topic} official documentation site")
   ```

2. Look for the documentation root URL (not a specific page). Priority order:
   - Official doc sites (docs.X.com, X.dev, X.readthedocs.io)
   - GitHub repository README or wiki
   - PyPI project page → Homepage link

3. Check if the site has a sitemap:
   - Try appending `/sitemap.xml` to the doc root
   - Try `/sitemap-index.xml` or `/sitemap_index.xml` as variants

### 3c: Fetch via sitemap (preferred for full coverage)

If you found a sitemap URL:

```
rlm_fetch_sitemap("https://example.com/docs/sitemap.xml")
```

This fetches every page in the sitemap and indexes each one. Rate-limited to avoid hammering the server (0.2s between requests). Returns a count of fetched vs. failed pages.

Sitemaps typically yield 20-200 pages, giving broad coverage of the entire doc site. This is the best approach when available.

### 3d: Fetch individual pages

If no sitemap exists, fetch the key documentation pages manually:

```
rlm_fetch("https://example.com/docs/quickstart")
rlm_fetch("https://example.com/docs/api-reference")
rlm_fetch("https://example.com/docs/configuration")
```

Prioritize these page types:
1. **Getting started / quickstart** — basic patterns, installation
2. **API reference** — function signatures, parameters, return types
3. **Configuration / settings** — environment variables, config files
4. **Tutorials** — common workflows and patterns
5. **FAQ / troubleshooting** — error resolution

Fetch 5-10 key pages maximum. Don't try to scrape an entire doc site page by page — that's what sitemaps are for.

### 3e: Load local files

If the documentation exists on disk (downloaded repo, vendor directory):

```
rlm_load_dir("path/to/docs/**/*.md")
```

This bulk-indexes all matching files. Useful for:
- Cloned library repos with docs/ directories
- Downloaded documentation archives
- Custom internal documentation

## Step 4: Verify Searchability

After indexing, confirm the content is actually findable. Run 2-3 verification searches targeting different aspects of the topic.

```
rlm_search("getting started {topic}")
rlm_search("core API {topic}")
```

What to check:
- **Results returned**: At least a few hits per query means indexing worked.
- **Relevancy scores**: Scores above 0.5 indicate strong matches. Below 0.3 suggests the content might not cover that aspect well.
- **Source attribution**: The hit titles should reference pages from the expected doc site.

If verification searches return nothing despite successful fetching, the content may have been fetched but not ingested properly. This can happen if the embedder failed silently. Check `rlm_knowledge_status()` to confirm the store grew in size.

## Step 5: Report Results

Summarize what happened in a concise report. The user wants to know what's now searchable and any gaps.

### Successful research report:

```
Researched: {topic}
Indexed: {N} pages from {source}
Key patterns found:
  - {pattern 1 from verification search}
  - {pattern 2 from verification search}

The knowledge store now covers {topic}. Use rlm_search("your query") to find specifics.
```

### Partial success report:

```
Researched: {topic}
Indexed: {N} pages (M failed)
Coverage: {what's there} — missing {what's not}

Suggestion: Try rlm_fetch("{specific_url}") for the missing sections.
```

### Failure report:

```
Could not fetch docs for {topic}.
Tried: rlm_research, WebSearch for official site, common URL patterns.
Issue: {what went wrong — blocked, no sitemap, site down}

You can paste content manually and I'll index it with rlm_ingest.
```

## Failure Modes and Recovery

### Blocked sites

Some sites block automated fetching (medium.com, substack.com, and others with aggressive bot protection). Don't retry — the fetcher has a built-in blocklist. Tell the user and suggest they paste the content.

### Empty sitemap

The sitemap exists but lists zero URLs, or all URLs fail to fetch. Fall back to individual page fetching (Step 3d).

### Rate limiting (HTTP 429)

The fetcher doesn't auto-retry on 429s. If a site rate-limits you, the pages just fail. Report the count and suggest the user try again later or fetch key pages individually.

### Content is HTML-heavy with little text

Some doc sites are mostly interactive (e.g. Swagger UIs, Jupyter notebooks). The fetcher converts HTML to markdown via html2text, but interactive content converts poorly. Note this in the report if search results seem thin despite many pages fetched.

### Already indexed — user wants refresh

If the user says "refresh" or "re-fetch", pass `force=True` mentally — but the skill-level tools don't expose force directly. Instead:
1. Call `rlm_knowledge_clear()` to wipe the existing index.
2. Re-run the research flow from Step 3.
3. Confirm the new index with Step 4.

## Known Libraries (Automatic Resolution)

The `rlm_research` tool has built-in URL mappings for these libraries, so it resolves them without any WebSearch:

fastapi, memvid, dspy, pydantic, httpx, starlette, uvicorn, sqlmodel, typer, polars, pytest, click, flask, django, numpy, pandas, scikit-learn, pytorch, transformers, langchain, llamaindex, openai, anthropic

For these topics, `rlm_research("{name}")` will work on the first try. For anything else, it attempts pattern matching (docs.X.com, X.dev, X.readthedocs.io, docs.X.io) before giving up.

For topics NOT in this list, `rlm_research` still tries common URL patterns. About half of popular Python libraries resolve this way. The other half need manual URL discovery (Step 3b).

## Multi-Topic Research

When the user asks to research multiple libraries at once ("research fastapi and pydantic"), run them sequentially:

1. `rlm_research("fastapi")` — wait for result
2. `rlm_research("pydantic")` — wait for result
3. Verify both with targeted searches
4. Report combined results

Don't try to merge them into a single call. Each `rlm_research` invocation handles one topic.

## Freshness and Re-Indexing

Fetched pages are cached as raw `.md` files under `.claude/docs/{library}/`. The cache TTL is 7 days — files older than that are re-fetched on the next `rlm_fetch` call. The `.mv2` index itself doesn't expire, but it reflects whatever content was last ingested.

If the user says the docs are outdated:
1. Run `rlm_knowledge_clear()` to wipe the search index.
2. Re-run the research flow. The fetcher will re-download stale cached files.
3. Verify the refreshed content.

## Rules

- **One fetch attempt per URL.** If a URL fails (blocked, timeout, 404), skip it. Don't retry.
- **Don't paste full doc content.** The point of indexing is to avoid filling the context window. Confirm what's indexed and give summaries, not full text.
- **Don't search and dump.** After verifying, don't run 10 searches and paste all results. Just confirm the index works.
- **Check before fetching.** Always run `rlm_knowledge_status()` first. Re-fetching already-indexed content wastes time and bandwidth.
- **Clear failures.** If nothing worked, say so explicitly and suggest alternatives. Don't silently move on.
- **Stay on topic.** If the user asked to research "fastapi", don't also fetch flask, django, and starlette "for good measure." Research what was asked.
