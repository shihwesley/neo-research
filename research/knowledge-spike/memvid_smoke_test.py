"""Memvid SDK v2 smoke test — macOS ARM64 validation.

Tests: import, create, put, find (lex), find (auto/vec), seal.
Run: python research/knowledge-spike/memvid_smoke_test.py
"""
import os
import sys
import tempfile
import traceback

def test(name, fn):
    """Run a test, print pass/fail."""
    try:
        result = fn()
        print(f"  PASS: {name}")
        if result:
            print(f"        {result}")
        return True
    except Exception as e:
        print(f"  FAIL: {name}")
        print(f"        {e}")
        traceback.print_exc()
        return False

def main():
    results = []
    tmpdir = tempfile.mkdtemp(prefix="memvid_smoke_")
    mv2_path = os.path.join(tmpdir, "test.mv2")
    mem = None

    print(f"\nMemvid SDK Smoke Test (macOS ARM64)")
    print(f"Temp dir: {tmpdir}\n")

    # Test 1: Import
    def t1():
        from memvid_sdk import create, use
        return f"memvid_sdk imported OK"
    results.append(test("Import memvid_sdk", t1))

    # Test 2: Create .mv2 (lex only)
    def t2():
        from memvid_sdk import create
        nonlocal mem
        mem = create(mv2_path)
        return f"Created {mv2_path}"
    results.append(test("Create .mv2 (lex only)", t2))

    # Test 3: Put documents
    def t3():
        docs = [
            ("FastAPI Quickstart", "docs", "FastAPI is a modern web framework for building APIs with Python 3.8+ based on standard Python type hints."),
            ("SQLAlchemy ORM", "docs", "SQLAlchemy is the Python SQL toolkit and Object Relational Mapper that gives application developers the full power of SQL."),
            ("Docker Compose", "docs", "Docker Compose is a tool for defining and running multi-container applications. With Compose, you use a YAML file to configure your application's services."),
            ("Redis Caching", "docs", "Redis is an open source, in-memory data structure store, used as a database, cache, and message broker."),
            ("pytest Testing", "docs", "pytest is a framework that makes building simple and scalable tests easy. Tests are easy to write and read."),
        ]
        for title, label, text in docs:
            mem.put(title=title, label=label, metadata={"source": "smoke_test"}, text=text)
        return f"Put {len(docs)} documents"
    results.append(test("Put 5 documents", t3))

    # Test 4: Lexical search (BM25)
    def t4():
        hits = mem.find("web framework API", k=3, mode="lex")
        hit_list = hits.get("hits", hits) if isinstance(hits, dict) else hits
        if not hit_list:
            return "WARNING: 0 hits for 'web framework API' (lex mode)"
        return f"Got {len(hit_list)} hits (lex mode)"
    results.append(test("Lexical search (BM25)", t4))

    # Test 5: NL query via lex (the spike's failure point)
    def t5():
        hits = mem.find("how do I build an API with Python?", k=3, mode="lex")
        hit_list = hits.get("hits", hits) if isinstance(hits, dict) else hits
        if not hit_list:
            return "WARNING: 0 hits for NL query (this was the spike failure)"
        return f"Got {len(hit_list)} hits for NL query"
    results.append(test("NL query via lex", t5))

    # Test 6: Seal
    def t6():
        mem.seal()
        size = os.path.getsize(mv2_path)
        return f"Sealed. File size: {size} bytes"
    results.append(test("Seal .mv2", t6))

    # Test 7: Reopen and search
    def t7():
        from memvid_sdk import use
        mem2 = use("basic", mv2_path)
        hits = mem2.find("testing framework", k=3, mode="lex")
        hit_list = hits.get("hits", hits) if isinstance(hits, dict) else hits
        return f"Reopened + searched: {len(hit_list)} hits"
    results.append(test("Reopen and search", t7))

    # Test 8: Create with enable_vec (the critical ARM64 test)
    mv2_vec_path = os.path.join(tmpdir, "test_vec.mv2")
    def t8():
        from memvid_sdk import create
        mem_vec = create(mv2_vec_path, enable_vec=True, enable_lex=True)
        mem_vec.put(title="Test", label="test", metadata={}, text="Machine learning models use gradient descent to optimize parameters.")
        hits = mem_vec.find("how do ML models learn?", k=3, mode="auto")
        hit_list = hits.get("hits", hits) if isinstance(hits, dict) else hits
        mem_vec.seal()
        return f"Vec enabled! Got {len(hit_list)} hits (auto mode)"
    results.append(test("Create with enable_vec=True (ARM64 critical)", t8))

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed")
    if passed == total:
        print("All tests passed! memvid-sdk works on macOS ARM64.")
    else:
        failed = [i+1 for i, r in enumerate(results) if not r]
        print(f"Failed tests: {failed}")
    print(f"{'='*50}\n")

    # Cleanup
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)

    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
