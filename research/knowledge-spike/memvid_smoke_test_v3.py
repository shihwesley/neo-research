"""Memvid SDK v2 smoke test v3 — test lex-only path + Ollama embeddings.

Findings so far:
- fastembed compiled out of macOS ARM64 wheel
- Need Ollama for local vec embeddings
- Test lex-only first, then try Ollama if available
"""
import os
import sys
import tempfile
import traceback
import time
import json
import urllib.request

def test(name, fn):
    try:
        t0 = time.time()
        result = fn()
        elapsed = time.time() - t0
        print(f"  PASS: {name} ({elapsed:.1f}s)")
        if result:
            print(f"        {result}")
        return True
    except Exception as e:
        print(f"  FAIL: {name}")
        print(f"        {type(e).__name__}: {e}")
        return False

def ollama_available():
    """Check if Ollama is running."""
    try:
        req = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        data = json.loads(req.read())
        models = [m["name"] for m in data.get("models", [])]
        return models
    except:
        return None

def main():
    results = []
    tmpdir = tempfile.mkdtemp(prefix="memvid_v3_")

    print(f"\nMemvid SDK Smoke Test v3")
    print(f"Temp dir: {tmpdir}")

    # Check Ollama
    ollama_models = ollama_available()
    if ollama_models:
        print(f"Ollama: running, models: {ollama_models}")
    else:
        print("Ollama: not running or not installed")

    print()

    # ===== Part A: Lex-only (no embeddings) =====
    print("--- Part A: Lex-only (BM25) ---")
    mv2_lex = os.path.join(tmpdir, "lex.mv2")
    mem = None

    docs = [
        ("FastAPI Quickstart", "docs", "FastAPI is a modern web framework for building APIs with Python based on standard type hints. It supports async await and generates automatic OpenAPI documentation."),
        ("SQLAlchemy ORM", "docs", "SQLAlchemy is the Python SQL toolkit and ORM. It provides a full suite of well known enterprise-level persistence patterns designed for efficient database access."),
        ("Docker Compose", "docs", "Docker Compose defines and runs multi-container applications using YAML configuration files for services, networks, and volumes."),
        ("Redis Caching", "docs", "Redis is an in-memory data structure store used as a database cache and message broker supporting strings hashes lists sets sorted sets."),
        ("pytest Framework", "docs", "pytest makes writing simple and scalable tests easy. It supports fixtures parameterization plugins and has a rich assertion introspection system."),
    ]

    def t_a1():
        from memvid_sdk import create
        nonlocal mem
        mem = create(mv2_lex)  # No enable_vec — lex only
        for title, label, text in docs:
            mem.put(title=title, label=label, metadata={"source": "test"}, text=text)
        return f"Created lex-only .mv2, put {len(docs)} docs"
    results.append(test("Create + put (lex only)", t_a1))

    def t_a2():
        hits = mem.find("FastAPI web framework", k=5, mode="lex")
        h = hits.get("hits", []) if isinstance(hits, dict) else hits
        previews = [x.get("preview", "?")[:50] if isinstance(x, dict) else str(x)[:50] for x in h[:2]]
        return f"{len(h)} hits. Top: {previews}"
    results.append(test("Lex search: 'FastAPI web framework'", t_a2))

    def t_a3():
        hits = mem.find("Python database access", k=5, mode="lex")
        h = hits.get("hits", []) if isinstance(hits, dict) else hits
        return f"{len(h)} hits"
    results.append(test("Lex search: 'Python database access'", t_a3))

    def t_a4():
        # NL query — BM25's weakness
        hits = mem.find("how do I test my Python code?", k=5, mode="lex")
        h = hits.get("hits", []) if isinstance(hits, dict) else hits
        return f"{len(h)} hits (NL via lex)"
    results.append(test("Lex search: NL 'how do I test my Python code?'", t_a4))

    def t_a5():
        answer = mem.ask("What tools are available for testing?", mode="lex", context_only=True)
        ctx = answer.get("context", "") if isinstance(answer, dict) else str(answer)
        has_content = len(str(ctx)) > 10
        return f"context_only response: {len(str(ctx))} chars, has content: {has_content}"
    results.append(test("ask() context_only (lex)", t_a5))

    def t_a6():
        mem.seal()
        size = os.path.getsize(mv2_lex)
        from memvid_sdk import use
        mem2 = use("basic", mv2_lex)
        hits = mem2.find("pytest", k=3, mode="lex")
        h = hits.get("hits", []) if isinstance(hits, dict) else hits
        return f"Sealed ({size}B), reopened, {len(h)} hits for 'pytest'"
    results.append(test("Seal + reopen + search", t_a6))

    # ===== Part B: Ollama embeddings (if available) =====
    if ollama_models:
        print("\n--- Part B: Ollama embeddings ---")

        # Check for embedding models
        embed_models = [m for m in ollama_models if any(x in m for x in ['embed', 'nomic', 'mxbai', 'bge'])]

        if not embed_models:
            print("  No embedding models found. Pulling nomic-embed-text...")
            os.system("ollama pull nomic-embed-text")
            embed_models = ["nomic-embed-text"]

        model_name = embed_models[0] if embed_models else "nomic-embed-text"
        print(f"  Using model: {model_name}")

        mv2_vec = os.path.join(tmpdir, "vec.mv2")
        mem_vec = None

        def t_b1():
            from memvid_sdk.embeddings import OllamaEmbeddings
            embedder = OllamaEmbeddings(model=model_name)
            return f"OllamaEmbeddings({model_name}): {embedder.dimension}d"
        results.append(test("OllamaEmbeddings init", t_b1))

        def t_b2():
            from memvid_sdk import create
            from memvid_sdk.embeddings import OllamaEmbeddings
            nonlocal mem_vec
            embedder = OllamaEmbeddings(model=model_name)
            mem_vec = create(mv2_vec, enable_vec=True, enable_lex=True)
            for title, label, text in docs:
                mem_vec.put(
                    title=title, label=label,
                    metadata={"source": "test"},
                    text=text,
                    embedder=embedder,
                )
            return f"Put {len(docs)} docs with Ollama embeddings"
        results.append(test("Put docs with Ollama embeddings", t_b2))

        def t_b3():
            from memvid_sdk.embeddings import OllamaEmbeddings
            embedder = OllamaEmbeddings(model=model_name)
            hits = mem_vec.find("how do I build a REST API with Python?", k=5, mode="sem", embedder=embedder)
            h = hits.get("hits", []) if isinstance(hits, dict) else hits
            previews = [x.get("preview", "?")[:60] if isinstance(x, dict) else str(x)[:60] for x in h[:3]]
            return f"Semantic: {len(h)} hits. Top: {previews}"
        results.append(test("Semantic search (NL query)", t_b3))

        def t_b4():
            from memvid_sdk.embeddings import OllamaEmbeddings
            embedder = OllamaEmbeddings(model=model_name)
            hits = mem_vec.find("container orchestration YAML", k=5, mode="auto", embedder=embedder)
            h = hits.get("hits", []) if isinstance(hits, dict) else hits
            return f"Hybrid: {len(h)} hits"
        results.append(test("Hybrid search (auto mode)", t_b4))

        def t_b5():
            from memvid_sdk.embeddings import OllamaEmbeddings
            embedder = OllamaEmbeddings(model=model_name)
            answer = mem_vec.ask("What is the best framework for building APIs?", mode="auto", context_only=True, embedder=embedder)
            if isinstance(answer, dict):
                ctx_len = len(str(answer.get("context", "")))
                hits_count = len(answer.get("hits", []))
                grounding = answer.get("grounding", {})
                return f"ask(auto): {hits_count} hits, {ctx_len} chars context, grounding: {grounding}"
            return f"Response type: {type(answer)}"
        results.append(test("ask() with Ollama (auto mode)", t_b5))

        def t_b6():
            mem_vec.seal()
            size = os.path.getsize(mv2_vec)
            from memvid_sdk import use
            from memvid_sdk.embeddings import OllamaEmbeddings
            embedder = OllamaEmbeddings(model=model_name)
            mem2 = use("basic", mv2_vec)
            hits = mem2.find("testing", k=3, mode="auto", embedder=embedder)
            h = hits.get("hits", []) if isinstance(hits, dict) else hits
            return f"Vec .mv2: {size}B, reopened, {len(h)} hits"
        results.append(test("Seal + reopen vec .mv2", t_b6))
    else:
        print("\n--- Part B: SKIPPED (Ollama not running) ---")
        print("  To enable: brew install ollama && ollama serve && ollama pull nomic-embed-text")

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed")
    print(f"{'='*50}\n")

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
