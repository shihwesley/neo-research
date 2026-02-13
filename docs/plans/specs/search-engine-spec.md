---
name: search-engine
phase: 4
sprint: 1
parent: null
depends_on: [search-spike]
status: draft
created: 2026-02-12
updated: 2026-02-13
---

# Memvid Knowledge Engine

## Overview
Memvid-backed knowledge store using `.mv2` files for hybrid search (BM25 + vector + reranker) over documentation. Replaces the FAISS+fastembed decision from the search spike. Each project gets one `.mv2` file. The MCP server manages the memvid lifecycle: create, open, ingest, search, close.

## Requirements
- [ ] REQ-1: One `.mv2` file per project at `~/.rlm-sandbox/knowledge/{project-hash}.mv2`
- [ ] REQ-2: Hybrid search via `find(mode='auto')` — BM25 + vector + reranker
- [ ] REQ-3: `rlm_search(query, top_k, mode)` MCP tool — returns ranked chunks with source attribution
- [ ] REQ-4: `rlm_ask(question, context_only)` MCP tool — RAG Q&A or context-only chunk retrieval
- [ ] REQ-5: `rlm_timeline(since, until)` MCP tool — chronological retrieval of indexed docs
- [ ] REQ-6: Local embeddings via fastembed-python (BGE-small-en-v1.5, 384d), Ollama as upgrade path, no API keys
- [ ] REQ-7: Adaptive retrieval enabled by default (score-cliff cutoff)
- [ ] REQ-8: Incremental indexing — new docs get embedded and indexed without rebuilding
- [ ] REQ-9: Index persistence — `.mv2` file survives MCP server restarts and `/clear`
- [ ] REQ-10: Entity extraction (Logic Mesh) as opt-in for API/class discovery in tech docs

## Acceptance Criteria
- [ ] AC-1: `rlm_search("async lifespan pattern")` returns relevant FastAPI doc chunks when those docs are loaded
- [ ] AC-2: Each result includes: chunk text, source doc name, section heading, relevance score, fetch timestamp
- [ ] AC-3: `rlm_ask("How does FastAPI handle startup?", context_only=True)` returns context chunks without LLM call
- [ ] AC-4: `rlm_timeline(since=<1hour_ago>)` returns docs fetched in the last hour
- [ ] AC-5: Cold query latency <50ms for 50 indexed documents (memvid claims ~5ms for 50K)
- [ ] AC-6: `.mv2` file reloads correctly after MCP server restart — no re-indexing needed
- [ ] AC-7: Adding a new doc and searching immediately finds content from that doc (WAL commit)
- [ ] AC-8: Smoke test passes on macOS ARM64: create .mv2, enable_vec=True, put 5 docs, find with mode='auto'

## Technical Approach

### Knowledge Store Manager (`mcp_server/knowledge.py`)

Central class that wraps memvid-sdk:

```python
from memvid_sdk import create, use
import os

class KnowledgeStore:
    def __init__(self, project_hash: str):
        self.path = f"~/.rlm-sandbox/knowledge/{project_hash}.mv2"
        self.mem = None

    def open(self):
        path = os.path.expanduser(self.path)
        if os.path.exists(path):
            self.mem = use('basic', path)
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.mem = create(path, enable_vec=True, enable_lex=True)

    def ingest(self, title, label, text, metadata=None):
        doc = {"title": title, "label": label, "metadata": metadata or {}, "text": text}
        self.mem.put_many([doc], embedder=self.embedder)  # put_many for Ollama embedding support

    def search(self, query, k=10, mode='auto'):
        return self.mem.find(query, k=k, mode=mode)

    def ask(self, question, context_only=True, mode='auto'):
        return self.mem.ask(question, mode=mode, context_only=context_only)

    def timeline(self, since=None, until=None, limit=20):
        return self.mem.timeline(since=since, until=until, limit=limit)

    def seal(self):
        self.mem.seal()
```

### Embedding Strategy

**Primary:** fastembed-python + BGE-small-en-v1.5 (384d, ~50MB model, ~120MB total deps)
- `pip install fastembed` — pure Python, ONNX Runtime, works on macOS ARM64
- 0.6s to embed 5 docs, 2-4ms search latency
- Zero external services — no Ollama, no API keys
- Custom `FastembedEmbeddings` wrapper (20 lines) implements memvid's `EmbeddingProvider` ABC

**Upgrade path:** Ollama + mxbai-embed-large (1024d) for higher quality embeddings.

**API pattern:** Use `put_many()` with `embedder=FastembedEmbeddings()`.
The `put()` method only supports memvid's internal Rust fastembed (broken on ARM64). `put_many()` accepts custom embedders.

**Fallback:** If fastembed import fails, fall back to lex-only (BM25). Warn user that semantic search is disabled.

### Search Modes Exposed

| MCP Tool | memvid Method | Mode | Use Case |
|----------|---------------|------|----------|
| rlm_search | find() | auto/lex/sem | Find relevant chunks |
| rlm_ask | ask(context_only=True) | auto | Get synthesized context for Claude |
| rlm_timeline | timeline() | time | Browse by recency |

### Entity Extraction (Opt-in)

For tech docs, entity extraction can identify API classes, functions, config keys. Uses local DistilBERT-NER (no API keys). Enabled via `rlm_enrich(engine='rules')` tool.

Not in critical path — can be Phase 5 if it slows things down.

## Files
| File | Action | Purpose |
|------|--------|---------|
| mcp_server/knowledge.py | create | KnowledgeStore class wrapping memvid-sdk |
| mcp_server/tools.py | modify | Register rlm_search, rlm_ask, rlm_timeline tools |
| tests/test_knowledge.py | create | Smoke test, search quality, persistence, incremental indexing |

## Tasks
1. Smoke test memvid-sdk on macOS ARM64 (create, enable_vec, put, find mode='auto')
2. Implement KnowledgeStore class (create/open/ingest/search/ask/timeline/seal)
3. Implement FastembedEmbeddings wrapper (EmbeddingProvider ABC, fastembed-python backend)
4. Register rlm_search, rlm_ask, rlm_timeline as MCP tools
5. Add adaptive retrieval configuration
6. Add index persistence and reload-on-restart
7. Write tests (smoke, search quality, incremental, persistence, timeline)

## Dependencies
- **Needs from search-spike:** hosting decision (host-side confirmed)
- **Needs from doc-fetcher:** raw document content for ingestion
- **Provides to orchestrator-integration:** rlm_search, rlm_ask, rlm_timeline tools

## Resolved Questions
- memvid replaces FAISS+fastembed — single .mv2 file instead of index + sidecar
- Host-side hosting — matches DSPy pattern, container stays lean
- Local embeddings via fastembed-python (pip install fastembed) — no API keys, no external services
- Adaptive retrieval on by default — better than fixed top-k for doc search
