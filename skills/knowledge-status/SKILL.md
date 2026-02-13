---
name: knowledge-status
description: Show what's indexed in the rlm-sandbox knowledge store — sources, chunk counts, file sizes. Use when the user asks what docs are available, what's been indexed, or wants a status check before searching.
---

# Knowledge Store Status

Check and report the current state of the rlm-sandbox knowledge store — what's indexed, how much, and what you can search.

## When This Skill Triggers

Use this skill when the user:
- Asks "what's indexed?" or "what docs do I have?"
- Wants to know if a library is searchable before using `rlm_search`
- Says "knowledge status", "check the store", or "what's in the knowledge base?"
- Needs to decide whether to run `/rlm-sandbox:research` or `rlm_fetch` before starting work

## Step 1: Call the Status Tool

Call the `rlm_knowledge_status()` MCP tool. No arguments needed — it uses the current project's hash automatically.

```
rlm_knowledge_status()
```

The tool returns a structured report with:
- **Store path**: Absolute path to the `.mv2` file (e.g. `~/.rlm-sandbox/knowledge/a3f8c1...mv2`)
- **Size**: File size in KB. A populated store is usually 500KB–50MB depending on content.
- **Status**: Either the size or "not created yet" if no indexing has happened.
- **Sources**: A per-library breakdown of raw `.md` files stored under `.claude/docs/{library}/`.

## Step 2: Interpret the Results

### Store exists and has sources

This is the normal state. Report it to the user with the library breakdown. The user can now call `rlm_search("query")` for any indexed library.

Example interpretation:
- Store is 2.4 MB with 3 libraries (fastapi: 47 files, pydantic: 23 files, httpx: 12 files)
- That's roughly 82 indexed pages, enough for typical API lookups
- The user can search across all three with a single `rlm_search` call

### Store exists but is small (< 100 KB)

A store under 100 KB usually means only a few pages got indexed — maybe a manual `rlm_ingest` call or a partial fetch. Warn the user that search coverage is thin. Suggest running `/rlm-sandbox:research <topic>` to build up the index.

### Store not created yet

The `.mv2` file doesn't exist. No indexing has happened for this project. This is normal for a fresh project or first-time plugin install.

Tell the user:
1. The store is empty — `rlm_search` will return nothing right now.
2. Suggest population strategies (see Step 3).

### Sources show libraries but store is missing or tiny

This means raw `.md` files exist in `.claude/docs/` (from prior `rlm_fetch` calls) but they weren't ingested into the `.mv2` index. This can happen if the server crashed during indexing or the store was cleared without clearing the raw files.

Suggest running `rlm_load_dir(".claude/docs/**/*.md")` to re-ingest the existing markdown files.

## Step 3: Suggest Population Strategies

When the store is empty or missing a library the user needs, recommend one of these approaches (in order of preference):

### Automatic: `/rlm-sandbox:research <topic>`

Best for common libraries. This skill handles everything — finds the doc site, fetches pages, indexes them. Works for any topic in the KNOWN_DOCS list (fastapi, dspy, pydantic, httpx, pytest, django, numpy, pandas, pytorch, transformers, etc.) and attempts pattern-matching for unknown topics.

Example:
```
/rlm-sandbox:research fastapi
```

### Manual URL: `rlm_fetch(url)`

When you know the exact documentation URL. Good for:
- Niche libraries not in the known docs mapping
- Specific API reference pages
- Blog posts or tutorials you want searchable

Example:
```
rlm_fetch("https://htmx.org/docs/")
```

### Bulk sitemap: `rlm_fetch_sitemap(sitemap_url)`

When a doc site has a sitemap. Fetches all pages listed in the sitemap XML and indexes each one. Best for comprehensive coverage of an entire doc site.

Example:
```
rlm_fetch_sitemap("https://fastapi.tiangolo.com/sitemap.xml")
```

### Local files: `rlm_load_dir(glob_pattern)`

When documentation is already on disk — downloaded repos, exported docs, or markdown collections. The glob pattern is relative to the project root.

Example:
```
rlm_load_dir("vendor/some-lib/docs/**/*.md")
```

### Manual ingest: `rlm_ingest(title, text)`

Last resort for small content. Paste specific text directly into the index. Useful for API responses, error messages, or snippets from paywalled sites.

## Step 4: Report to the User

Format the status report as a concise summary. The user cares about what's searchable and what's missing, not internal details like project hashes.

Good report format:

```
Knowledge store: 3 libraries indexed (2.4 MB)
  - fastapi: 47 pages
  - pydantic: 23 pages
  - httpx: 12 pages

Ready to search. Use rlm_search("your query") to find relevant docs.
```

If the store is empty:

```
Knowledge store is empty — no docs indexed yet.

To populate it:
  /rlm-sandbox:research fastapi    (automatic — finds and indexes docs)
  rlm_fetch("https://url")         (manual — fetch a specific page)
```

## Common Scenarios

### "I'm about to implement feature X — do I have the right docs?"

This is the most common trigger. The user is starting implementation and wants to confirm they can look up API details as they go. Run the status check, then tell them which libraries are indexed and whether the coverage is sufficient. If a key dependency is missing, suggest the research skill before they start coding.

### "Search results are bad — is the index stale?"

When `rlm_search` returns irrelevant results despite the store having content, run status to check:
- **Store size is reasonable but results are poor**: The embedder may have fallen back to BM25-only mode. Vector search gives better results for semantic queries. Check if `sentence-transformers` is installed.
- **Store is very large (>50MB)**: The index may contain too much noise from bulk fetches. Suggest clearing and re-indexing only the relevant libraries.
- **Sources show the library but results miss obvious content**: The pages might have been fetched but contain mostly navigation HTML, not actual documentation. Re-fetch with individual page URLs targeting the content pages specifically.

### "How do I add my own notes to the store?"

The user wants to index their own content — meeting notes, architecture decisions, internal docs. Point them to `rlm_ingest(title, text)` for small items or `rlm_load_dir("path/**/*.md")` for bulk loading. These get the same hybrid search treatment as fetched documentation.

### "I want to start fresh"

Call `rlm_knowledge_clear()` to wipe the `.mv2` index. This preserves raw `.md` files in `.claude/docs/`, so previously fetched content can be re-ingested. If the user also wants to clear the raw cache, they need to delete `.claude/docs/` manually.

## Search Modes Reference

When suggesting follow-up searches after checking status, the user may want to know about search modes:

| Mode | What it does | Best for |
|------|-------------|----------|
| `auto` | BM25 + vector fusion (default) | General queries — "how does X work?" |
| `vec` | Vector similarity only | Conceptual queries — "patterns like dependency injection" |
| `lex` | BM25 keyword match only | Exact term lookups — "ValidationError class" |

The default `auto` mode works well for most queries. Suggest `lex` when the user searches for specific class names, function signatures, or error messages.

## Error Handling

### Embedder unavailable

The knowledge store falls back to lexical-only (BM25) search when the sentence-transformers embedder can't load. This is noted in server logs but not always visible to the user. If search results seem poor despite having content indexed, mention this possibility — reinstalling `sentence-transformers` or running `scripts/setup.sh` again usually fixes it.

### Permission errors on ~/.rlm-sandbox/knowledge/

The knowledge directory defaults to `~/.rlm-sandbox/knowledge/`. If the user gets permission errors, the directory either doesn't exist (run `scripts/setup.sh`) or has wrong ownership.

### Store corruption

Rare, but if the `.mv2` file is corrupted (partial write during crash), `rlm_knowledge_clear()` wipes it so a fresh index can be built. The raw `.md` files in `.claude/docs/` survive clearing, so they can be re-ingested with `rlm_load_dir`.

## Quick Tool Reference

For convenience, here are all knowledge-related MCP tools the user might ask about after checking status:

| Tool | Purpose | Needs Docker? |
|------|---------|---------------|
| `rlm_search(query, top_k, mode)` | Hybrid search over indexed docs | No |
| `rlm_ask(question, context_only)` | RAG Q&A or context-only retrieval | No |
| `rlm_timeline(since, until)` | Browse docs by recency | No |
| `rlm_ingest(title, text)` | Manually add content to index | No |
| `rlm_fetch(url)` | Fetch URL → .md + .mv2 | No |
| `rlm_fetch_sitemap(sitemap_url)` | Bulk fetch from sitemap | No |
| `rlm_load_dir(glob)` | Bulk load local files | No |
| `rlm_research(topic)` | Find, fetch, and index docs | No |
| `rlm_knowledge_status()` | This tool — show what's indexed | No |
| `rlm_knowledge_clear()` | Wipe the .mv2 index | No |

None of the knowledge tools require Docker. They work on any machine with the Python venv set up.

## Rules

- Call `rlm_knowledge_status()` once — don't call it repeatedly in the same interaction.
- Don't display the full store path or project hash to the user unless they ask. These are internal details.
- If suggesting population strategies, pick the most appropriate one for the user's situation — don't list all four every time.
- When the store has content, your job is done after reporting. Don't preemptively search for anything unless the user asks.
