"""Memvid SDK v2 smoke test — round 2 with proper embedding params.

The first test showed vec doesn't crash on ARM64, but we need enable_embedding=True on put().
"""
import os
import sys
import tempfile
import traceback
import time

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
        traceback.print_exc()
        return False

def main():
    results = []
    tmpdir = tempfile.mkdtemp(prefix="memvid_v2_")
    mv2_path = os.path.join(tmpdir, "test.mv2")

    print(f"\nMemvid SDK Smoke Test v2 (with embeddings)")
    print(f"Temp dir: {tmpdir}\n")

    docs = [
        ("FastAPI Quickstart", "docs", "FastAPI is a modern web framework for building APIs with Python 3.8+ based on standard Python type hints. It supports async/await and has automatic OpenAPI documentation."),
        ("SQLAlchemy ORM", "docs", "SQLAlchemy is the Python SQL toolkit and Object Relational Mapper that gives application developers the full power and flexibility of SQL. It provides a generative query system."),
        ("Docker Compose", "docs", "Docker Compose is a tool for defining and running multi-container applications. With Compose, you use a YAML file to configure your application's services and networking."),
        ("Redis Caching", "docs", "Redis is an open source, in-memory data structure store, used as a database, cache, and message broker. It supports strings, hashes, lists, sets, and sorted sets."),
        ("pytest Testing", "docs", "pytest is a framework that makes building simple and scalable tests easy. Tests are easy to write and read. It supports fixtures, parameterization, and plugins."),
    ]

    # Test 1: Create with vec + lex enabled
    mem = None
    def t1():
        from memvid_sdk import create
        nonlocal mem
        mem = create(mv2_path, enable_vec=True, enable_lex=True)
        return "Created with enable_vec=True, enable_lex=True"
    results.append(test("Create .mv2 with vec + lex", t1))

    # Test 2: Put docs with embeddings enabled
    def t2():
        for title, label, text in docs:
            mem.put(
                title=title,
                label=label,
                metadata={"source": "smoke_test"},
                text=text,
                enable_embedding=True,
                embedding_model="bge-small",
            )
        return f"Put {len(docs)} documents with enable_embedding=True"
    results.append(test("Put docs with embeddings (may download model)", t2))

    # Test 3: Lex search — keyword query
    def t3():
        hits = mem.find("web framework API", k=5, mode="lex")
        hit_list = hits.get("hits", []) if isinstance(hits, dict) else hits
        return f"Lex keyword search: {len(hit_list)} hits"
    results.append(test("Lex search (keyword)", t3))

    # Test 4: Semantic search — NL query
    def t4():
        hits = mem.find("how do I build a REST API with Python?", k=5, mode="sem")
        hit_list = hits.get("hits", []) if isinstance(hits, dict) else hits
        if not hit_list:
            # try mode="vec" or mode="auto" as alternatives
            hits2 = mem.find("how do I build a REST API with Python?", k=5, mode="auto")
            hit_list2 = hits2.get("hits", []) if isinstance(hits2, dict) else hits2
            return f"sem: 0 hits, auto: {len(hit_list2)} hits"
        return f"Semantic search: {len(hit_list)} hits"
    results.append(test("Semantic search (NL query)", t4))

    # Test 5: Hybrid/auto search
    def t5():
        hits = mem.find("container orchestration YAML", k=5, mode="auto")
        hit_list = hits.get("hits", []) if isinstance(hits, dict) else hits
        return f"Auto/hybrid: {len(hit_list)} hits"
    results.append(test("Hybrid search (auto mode)", t5))

    # Test 6: ask() with context_only
    def t6():
        answer = mem.ask("What web frameworks are mentioned?", mode="lex", context_only=True)
        if isinstance(answer, dict):
            ctx = answer.get("context", answer.get("hits", "?"))
            return f"ask(context_only=True): got response (keys: {list(answer.keys())})"
        return f"ask returned: {type(answer)}"
    results.append(test("ask() with context_only=True", t6))

    # Test 7: Seal + reopen + search
    def t7():
        mem.seal()
        from memvid_sdk import use
        mem2 = use("basic", mv2_path)
        hits = mem2.find("testing framework", k=3, mode="lex")
        hit_list = hits.get("hits", []) if isinstance(hits, dict) else hits
        size = os.path.getsize(mv2_path)
        return f"Sealed ({size} bytes), reopened, searched: {len(hit_list)} hits"
    results.append(test("Seal + reopen + search", t7))

    # Test 8: Inspect hit structure
    def t8():
        from memvid_sdk import use
        mem2 = use("basic", mv2_path)
        hits = mem2.find("Python web framework", k=1, mode="lex")
        if isinstance(hits, dict):
            hit_list = hits.get("hits", [])
            if hit_list:
                h = hit_list[0]
                return f"Hit keys: {list(h.keys()) if isinstance(h, dict) else type(h)}"
            return f"No hits. Response keys: {list(hits.keys())}"
        return f"Response type: {type(hits)}"
    results.append(test("Inspect hit structure", t8))

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed")
    if passed == total:
        print("All tests passed!")
    else:
        failed = [i+1 for i, r in enumerate(results) if not r]
        print(f"Failed tests: {failed}")
    print(f"{'='*50}\n")

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
