# Research Pipeline v2 — "Matrix Download"

## Goal

Replace the current agent zoo (rlm-researcher, rlm-sandbox, research-sandbox, research-specialist) with a single unified research pipeline. One agent runs the full cycle: structured research design → format-agnostic acquisition → REPL-based distillation → expertise artifact. The agent becomes a genuine expert on the topic without blowing the context window.

## Priority

Quality — get the distillation step right. This is the missing piece that makes everything else worthwhile.

## Mode

Task-based, 5 phases.

## Input Contract

The `/research` skill accepts any of:
- Simple topic: `"WebTransport protocol"`
- Rich prompt: `"I need to understand how SwiftUI NavigationStack works in iOS 17+, especially the programmatic navigation and deep linking patterns"`
- Prompt with URLs: `"Learn about TCA — here's the repo https://github.com/pointfreeco/swift-composable-architecture and their docs site"`
- Mixed: paragraph of context + partial knowledge + links + specific questions

Phase 1 (Input Parsing) handles all these shapes.

## Output Contract

Two artifacts per research topic:

1. **Expertise artifact** (`expertise.md`, 3-5K tokens)
   - Structured mental model of the topic
   - Key concepts, patterns, APIs, gotchas
   - Code examples where applicable
   - Loaded into agent context = instant expertise

2. **Knowledge store** (`knowledge.mv2`)
   - Full indexed content, queryable via rlm_search/rlm_ask
   - For deep-dives beyond the expertise doc

Both live at `~/.claude/research/<topic-slug>/`.

## Storage Layout

```
~/.claude/research/
├── <topic-slug>/
│   ├── expertise.md       # The Matrix download (3-5K tokens)
│   ├── knowledge.mv2      # Full knowledge store (hybrid search)
│   ├── sources.json       # Fetch metadata: URLs, dates, formats, byte counts
│   └── question-tree.md   # Research design (resumable)
```

Central location. Accessible from any project or working directory. No scattering.

---

## Phase 1: Input Parsing & Research Design

**Goal:** Turn freeform input into a structured question tree.

### Tasks

1. **Parse input** — Extract: topic name, context/background, seed URLs, specific questions, scope hints.

2. **Build question tree** — Decompose topic into 4-7 research branches:
   ```
   Topic: "<extracted topic>"
   ├── What is it? (definition, purpose, problem it solves)
   ├── How does it work? (architecture, mechanics, data flow)
   ├── Official sources (specs, RFCs, official docs, repos)
   ├── API / interface surface (key types, methods, patterns)
   ├── Real-world usage (examples, tutorials, adoption)
   ├── Gotchas & limitations (known issues, version-specific, caveats)
   └── Alternatives & comparisons (what else exists, tradeoffs)
   ```
   Not every branch applies to every topic. The agent adapts the tree to the domain.

3. **Source strategy per branch** — For each branch, identify source types:
   - Official docs / specs → direct URLs if known
   - GitHub repos → search for primary repo
   - Academic papers → arxiv, ACM if applicable
   - Community content → blog posts, tutorials (lower priority)

4. **Write question-tree.md** to `~/.claude/research/<slug>/question-tree.md`

5. **Create sources.json** (empty, populated during Phase 2)

### Quality gate
The question tree should have 4-7 branches. Each branch should have at least one target source type. If the user provided seed URLs, they should be assigned to the right branches.

---

## Phase 2: Source Discovery

**Goal:** Find authoritative URLs for each branch of the question tree.

### Tasks

1. **WebSearch per branch** — 1-2 targeted searches per question tree branch. Not "search <topic>" — search for the specific thing each branch needs:
   - "What is it?" → search for official introduction / overview
   - "How does it work?" → search for architecture docs, protocol specs
   - "API surface" → search for API reference, type docs
   - etc.

2. **Rank and filter sources** — Prioritize:
   - Official docs (tier 1)
   - Primary repos / RFCs / specs (tier 1)
   - Tutorials by maintainers or known experts (tier 2)
   - Community blog posts (tier 3)
   - Skip: SEO spam, aggregator sites, outdated (>2yr unless stable spec)

3. **Collect URL list** — Deduplicate. Assign each URL to its question tree branch. Target: 8-20 URLs total (not 50 — quality over quantity).

4. **Update sources.json** with discovered URLs and branch assignments.

### Quality gate
Each question tree branch should have 1-4 assigned URLs. At least 50% should be tier 1 (official/primary). Total 8-20 URLs.

---

## Phase 3: Acquisition

**Goal:** Fetch all content to disk and index into .mv2. Zero context cost.

### Tasks

1. **Create topic directory:**
   ```bash
   mkdir -p ~/.claude/research/<slug>
   mkdir -p /tmp/research-<slug>   # temp fetch dir
   ```

2. **Fetch cascade per URL** (markdown-first):
   ```
   markdown.new/<url>  →  Accept: text/markdown  →  raw fetch  →  skip
   ```
   For PDFs: `curl → pdftotext` (if available) or store raw.
   For JSON APIs: store directly.
   Minimum 500 bytes or skip (error pages).

3. **Batch fetch script** — Write a shell script, run it once. Output: one status line per URL. Agent never reads fetched content.

4. **Index into knowledge store:**
   ```bash
   # Per file, with branch tag as label:
   $KNOWLEDGE_CLI ingest --project <slug> --title "<url>" --label "<branch>" < /tmp/file.md
   ```
   Or use rlm_ingest MCP tool if available.

5. **Update sources.json** with fetch results: status (ok/fail), format (md.new/accept/raw/pdf), byte count, branch label.

6. **Verify indexing** — Run 2-3 test searches against the knowledge store to confirm content is findable.

### Quality gate
- 70%+ of URLs successfully fetched and indexed
- Test searches return relevant results
- sources.json fully populated

---

## Phase 4: Distillation (The Matrix Download)

**Goal:** Transform indexed knowledge into a compact expertise artifact. This is the critical phase.

### Strategy

The agent uses `rlm_exec` to run Python in the sandbox. The Python code:
1. Queries the knowledge store systematically (one query per question tree branch)
2. Collects the top results for each branch
3. The agent reads these results (targeted excerpts, not full pages)
4. Synthesizes into the expertise artifact

**Why the sandbox?** The sandbox can run programmatic queries against the .mv2 store, process results, and return structured data — all within the sandbox's context, not the main agent's. The agent only sees the final structured output.

### Tasks

1. **Systematic extraction** — For each question tree branch:
   ```python
   # In sandbox via rlm_exec:
   from memvid_sdk import use
   mem = use("basic", "~/.claude/research/<slug>/knowledge.mv2",
             enable_vec=True, enable_lex=True)

   results = mem.search("what is <topic> and what problem does it solve", top_k=5)
   # Return top excerpts for this branch
   ```

   Or use MCP tools:
   ```
   rlm_search(query="<branch question>", project="<slug>", top_k=5)
   ```

2. **Cross-branch synthesis** — After extracting from all branches, the agent has targeted excerpts (maybe 10-15K tokens total from 5-7 branches × ~2K each). This is manageable. The agent synthesizes these into the expertise doc.

3. **Write expertise.md** — Structured format:
   ```markdown
   # <Topic> — Expertise Artifact

   ## Mental Model
   [2-3 paragraphs: what it is, why it exists, how it fits in the ecosystem]

   ## Architecture / How It Works
   [Key mechanics, data flow, protocol layers — whatever applies]

   ## Key APIs / Interfaces
   [Primary types, methods, patterns — with brief code examples]

   ## Common Patterns
   [How people actually use this in practice]

   ## Gotchas & Pitfalls
   [Known issues, version-specific caveats, common mistakes]

   ## Quick Reference
   [Cheat-sheet style: most-used APIs, config options, CLI commands]
   ```

4. **Validate expertise** — Run a few "test questions" against the expertise doc mentally. Does it answer the kinds of questions you'd need in practice? If gaps, run additional targeted queries against the knowledge store.

### Quality gate
- Expertise doc is 3-5K tokens (not bloated, not skeletal)
- Covers all question tree branches
- Contains concrete examples, not just abstractions
- A developer reading it could start working with the topic

---

## Phase 5: Loading & Cleanup

**Goal:** Make the expertise immediately usable and clean up temp files.

### Tasks

1. **Load expertise into context** — Read and present `expertise.md` to the current session. Agent now "knows" the topic.

2. **Register for future sessions** — The expertise doc at `~/.claude/research/<slug>/expertise.md` can be referenced in CLAUDE.md or read on demand via `/research load <topic>`.

3. **Cleanup temp files:**
   ```bash
   rm -rf /tmp/research-<slug>
   ```

4. **Summary report** — Brief output:
   ```
   Research complete: <topic>
   - Sources: N fetched, M indexed
   - Knowledge store: ~/.claude/research/<slug>/knowledge.mv2
   - Expertise: ~/.claude/research/<slug>/expertise.md (N tokens)
   - Deep-dive: rlm_search(query="...", project="<slug>")
   ```

---

## Agent Design

**One agent replaces four.** Name: `research-agent` (or keep `rlm-researcher` and rewrite it).

Frontmatter:
```yaml
name: research-agent
description: >
  Unified research pipeline. Builds question tree, discovers and fetches sources
  (zero context cost), indexes into .mv2, distills via REPL into compact expertise
  artifact. Agent becomes domain expert without fine-tuning.
model: sonnet
tools: Bash, Read, Write, Glob, Grep, WebSearch, ToolSearch
```

The agent runs all 5 phases sequentially. No handoffs, no spawning sub-agents, no coordination overhead.

**Skill entry point:** `/research <input>`

The skill:
1. Parses the input (could be topic, paragraph, URLs, or mix)
2. Spawns the research-agent with the parsed input
3. Agent runs the pipeline
4. Returns: expertise doc loaded + summary

---

## What Gets Deleted

After this redesign ships:
- `agents/rlm-researcher.md` → replaced by `agents/research-agent.md`
- `agents/rlm-sandbox.md` → keep (sandbox execution is still a valid standalone use case)
- `agents/research-sandbox.md` → delete (absorbed into research-agent)
- `agents/research-specialist.md` → delete (absorbed into research-agent)
- Global copies in `~/.claude/agents/` and `Source/.claude/agents/` → clean up

---

## Dependencies

- `rlm_exec` MCP tool (for sandbox distillation queries) — exists
- `rlm_search` / `rlm_ask` / `rlm_ingest` MCP tools — exist
- `memvid_sdk` with enable_vec/enable_lex — fixed in v1.3.0
- `markdown.new` for HTML→markdown — external service, no setup needed
- `pdftotext` for PDF handling — optional, degrade gracefully

## Risk

The distillation quality depends on how well the systematic queries capture the knowledge. If the question tree branches are too broad, the excerpts will be shallow. Mitigation: the agent can run follow-up queries on any branch that feels thin before writing the expertise doc.
