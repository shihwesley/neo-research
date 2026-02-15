#!/usr/bin/env python3
"""End-to-end validation of apple docs pipeline + recursive LLM execution.

Requires:
- Docker sandbox running on :8080
- DocSetQuery tools at /Users/quartershots/Source/DocSetQuery/tools/
- ANTHROPIC_API_KEY env var (for LLM callback test)

Run: .venv/bin/python tests/e2e_validate.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.llm_callback import LLMCallbackServer
from mcp_server.sub_agent import inject_llm_stub
from mcp_server.apple_docs import (
    DOCSET_QUERY_ROOT,
    TOOLS_DIR,
    _run_tool,
    _parse_search_results,
    _chunk_markdown,
)

SANDBOX_URL = "http://localhost:8080"
CALLBACK_PORT = 18090  # use non-default port to avoid conflicts


def header(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def skip(msg: str) -> None:
    print(f"  [SKIP] {msg}")


# ---------------------------------------------------------------------------
# Test 1: Apple docs — docindex search
# ---------------------------------------------------------------------------

async def test_apple_search() -> bool:
    header("Test 1: rlm_apple_search — docindex search")

    docindex = TOOLS_DIR / "docindex.py"
    if not docindex.exists():
        skip(f"DocSetQuery not found at {TOOLS_DIR}")
        return False

    # Search for "Observable"
    rc, stdout, stderr = await _run_tool([
        str(docindex), "search", "Observable",
    ])
    if rc != 0:
        fail(f"docindex search failed (rc={rc}): {stderr.strip()}")
        return False

    results = _parse_search_results(stdout)
    if not results:
        fail("No results for 'Observable'")
        return False

    ok(f"Found {len(results)} results for 'Observable'")
    for r in results[:3]:
        print(f"    - {r['title']}: {r['heading']} ({r['path']})")

    return True


# ---------------------------------------------------------------------------
# Test 2: Apple docs — export + chunk pipeline
# ---------------------------------------------------------------------------

async def test_apple_export() -> bool:
    header("Test 2: rlm_apple_export pipeline — export + sanitize + chunk")

    export_tool = TOOLS_DIR / "docset_query.py"
    sanitize_tool = TOOLS_DIR / "docset_sanitize.py"

    if not export_tool.exists():
        skip(f"docset_query.py not found at {TOOLS_DIR}")
        return False

    output_path = Path("/tmp/rlm-e2e-swiftui.md")
    output_path.unlink(missing_ok=True)

    # Export SwiftUI docs (depth=2 for speed)
    rc, stdout, stderr = await _run_tool([
        str(export_tool),
        "export",
        "--root", "/documentation/swiftui",
        "--output", str(output_path),
        "--max-depth", "2",
    ])
    if rc != 0:
        fail(f"Export failed (rc={rc}): {stderr.strip()[:300]}")
        return False

    if not output_path.exists():
        fail("Export produced no output file")
        return False

    text = output_path.read_text()
    ok(f"Exported SwiftUI docs: {len(text)} bytes")

    # Sanitize
    rc, stdout, stderr = await _run_tool([
        str(sanitize_tool),
        "--input", str(output_path),
        "--in-place",
        "--toc-depth", "2",
    ])
    if rc != 0:
        print(f"    (sanitize warning rc={rc}, continuing)")

    text = output_path.read_text()
    chunks = _chunk_markdown(text, "swiftui")
    ok(f"Chunked into {len(chunks)} sections")

    # Verify chunks have expected shape
    if len(chunks) < 3:
        fail(f"Too few chunks ({len(chunks)}), expected more for SwiftUI")
        return False

    for c in chunks[:3]:
        print(f"    - {c['title']} ({len(c['text'])} chars)")

    # Search the exported file for NavigationStack
    if "NavigationStack" in text or "navigationstack" in text.lower():
        ok("NavigationStack found in exported content")
    else:
        print("    (NavigationStack not in depth-2 export — expected at higher depth)")

    output_path.unlink(missing_ok=True)
    return True


# ---------------------------------------------------------------------------
# Test 3: Sandbox basic exec (pre-check)
# ---------------------------------------------------------------------------

async def test_sandbox_basic() -> bool:
    header("Test 3: Sandbox basic exec (pre-check)")

    async with httpx.AsyncClient(base_url=SANDBOX_URL, timeout=10) as client:
        r = await client.post("/exec", json={"code": "print(2 + 2)"})
        if r.status_code != 200:
            fail(f"Sandbox /exec returned {r.status_code}")
            return False

        data = r.json()
        output = data.get("output", "").strip()
        if output == "4":
            ok("Sandbox exec works: 2+2=4")
            return True
        else:
            fail(f"Expected '4', got '{output}'")
            return False


# ---------------------------------------------------------------------------
# Test 4: Recursive LLM execution — inject stub + callback
# ---------------------------------------------------------------------------

async def test_recursive_llm() -> bool:
    header("Test 4: Recursive LLM execution — llm_query() callback")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        skip("ANTHROPIC_API_KEY not set — cannot test live LLM callback")
        return False

    callback = LLMCallbackServer(port=CALLBACK_PORT)
    await callback.start()

    try:
        # Inject llm_query() stub into the sandbox
        async with httpx.AsyncClient(base_url=SANDBOX_URL, timeout=10) as client:
            cb_url = f"http://host.docker.internal:{CALLBACK_PORT}/llm_query"
            await inject_llm_stub(client, cb_url)
            ok("Injected llm_query() stub into sandbox")

            # Verify the function exists
            r = await client.post("/exec", json={"code": "print(type(llm_query))"})
            data = r.json()
            output = data.get("output", "").strip()
            if "function" in output:
                ok(f"llm_query exists in sandbox: {output}")
            else:
                fail(f"llm_query not found: {output}")
                return False

            # Call llm_query from inside the sandbox
            r = await client.post(
                "/exec",
                json={
                    "code": 'result = llm_query("What is 2+2? Reply with just the number.")\nprint(result)',
                    "timeout": 30,
                },
                timeout=35,
            )
            data = r.json()
            output = data.get("output", "").strip()
            stderr = data.get("stderr", "").strip()

            if output:
                ok(f"llm_query returned: {output[:200]}")
                # Check if the response mentions "4" anywhere
                if "4" in output:
                    ok("Response contains expected answer (4)")
                else:
                    print(f"    (response doesn't contain '4' but LLM routing worked)")
                return True
            else:
                fail(f"llm_query returned no output. stderr: {stderr[:300]}")
                return False

    finally:
        await callback.stop()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    print("\nrlm-sandbox E2E Validation")
    print("=" * 60)

    results = {}

    # Pre-check: sandbox is alive
    results["sandbox_basic"] = await test_sandbox_basic()

    if not results["sandbox_basic"]:
        print("\nSandbox not responding. Aborting remaining tests.")
        sys.exit(1)

    # Apple docs tests
    results["apple_search"] = await test_apple_search()
    results["apple_export"] = await test_apple_export()

    # Recursive LLM test
    results["recursive_llm"] = await test_recursive_llm()

    # Summary
    header("Summary")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    skipped = sum(1 for v in results.values() if v is False)  # rough
    print(f"  {passed}/{total} passed")
    for name, result in results.items():
        status = "PASS" if result else "FAIL/SKIP"
        print(f"    {name}: {status}")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
