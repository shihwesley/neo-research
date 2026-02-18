#!/usr/bin/env python3
"""CLI bridge to the neo-research knowledge store.

Bypasses MCP so subagents can index research data via Bash.
Same KnowledgeStore, same .mv2 files, no MCP connection needed.

Handles missing sentence-transformers gracefully (lex-only fallback).

Usage:
    knowledge ingest --title "Page Title" --label "topic" < content.txt
    knowledge ingest --title "Page Title" --label "topic" --text "inline text"
    knowledge ingest-batch < docs.jsonl
    knowledge search "query string" [--top-k 10]
    knowledge ask "question"
    knowledge status
    knowledge audit                    # list previously researched topics
    knowledge audit --reindex          # re-ingest local docs into store
    knowledge audit --refetch          # re-fetch from source URLs
    knowledge audit --topic fastapi    # limit to one topic
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path so we can import mcp_server modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from mcp_server.knowledge import KnowledgeStore, get_store, _project_hash

# Suppress warnings to keep agent output clean (lex-only fallback is fine)
logging.basicConfig(level=logging.ERROR)
log = logging.getLogger(__name__)


def _safe_embedder(store: KnowledgeStore):
    """Get the embedder, returning None if sentence-transformers isn't installed.

    The KnowledgeStore.embedder property creates a lazy wrapper that doesn't
    fail until embed_documents() is called. We probe it here and fall back
    to None (lex-only BM25) if the actual model can't load.
    """
    emb = store.embedder
    if emb is None:
        return None
    # probe: try to embed a single token to force the lazy import
    try:
        emb.embed_documents(["test"])
        return emb
    except (ImportError, Exception) as exc:
        log.warning("Embedder unavailable, using lex-only: %s", exc)
        return None


def _open_store(project: str | None) -> tuple[KnowledgeStore, object]:
    """Open store and resolve embedder. Returns (store, embedder_or_None)."""
    store = get_store(project)
    store.open()
    embedder = _safe_embedder(store)
    return store, embedder


def cmd_ingest(args: argparse.Namespace) -> None:
    """Ingest a single document. Reads text from --text or stdin."""
    text = args.text
    if not text:
        text = sys.stdin.read()

    if not text.strip():
        print("Error: no text provided (use --text or pipe to stdin)", file=sys.stderr)
        sys.exit(1)

    store, embedder = _open_store(args.project)

    doc = {
        "title": args.title,
        "label": args.label,
        "text": text,
        "metadata": {},
    }
    frame_ids = store.mem.put_many([doc], embedder=embedder)
    store.close()  # seal() persists the data

    print(json.dumps({
        "ok": True,
        "title": args.title,
        "chars": len(text),
        "frames": len(frame_ids),
        "mode": "hybrid" if embedder else "lex-only",
    }))


def cmd_ingest_batch(args: argparse.Namespace) -> None:
    """Batch ingest from JSONL on stdin. Each line: {"title": "...", "text": "...", "label": "..."}"""
    store, embedder = _open_store(args.project)

    docs = []
    for line_num, line in enumerate(sys.stdin, 1):
        line = line.strip()
        if not line:
            continue
        try:
            doc = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"Error on line {line_num}: {e}", file=sys.stderr)
            continue

        if "title" not in doc or "text" not in doc:
            print(f"Skipping line {line_num}: missing 'title' or 'text'", file=sys.stderr)
            continue
        docs.append({
            "title": doc["title"],
            "label": doc.get("label", "kb"),
            "text": doc["text"],
            "metadata": doc.get("metadata", {}),
        })

    if not docs:
        print("Error: no valid documents on stdin", file=sys.stderr)
        sys.exit(1)

    frame_ids = store.mem.put_many(docs, embedder=embedder)
    store.close()  # seal() persists the data

    print(json.dumps({
        "ok": True,
        "documents": len(docs),
        "frames": len(frame_ids),
        "total_chars": sum(len(d["text"]) for d in docs),
        "mode": "hybrid" if embedder else "lex-only",
    }))


def cmd_search(args: argparse.Namespace) -> None:
    """Search the knowledge store."""
    store, embedder = _open_store(args.project)

    # Use lex mode if no embedder, auto otherwise
    mode = "auto" if embedder else "lex"
    results = store.mem.find(
        args.query,
        k=args.top_k,
        mode=mode,
        embedder=embedder,
    )
    hits = results.get("hits", [])

    output = []
    for hit in hits:
        output.append({
            "title": hit.get("title", ""),
            "score": round(hit.get("score", 0), 4),
            "snippet": hit.get("snippet", hit.get("text", ""))[:500],
        })

    print(json.dumps({"hits": output, "count": len(output)}))


def cmd_ask(args: argparse.Namespace) -> None:
    """RAG Q&A over the knowledge store."""
    question = args.question or sys.stdin.read().strip()
    if not question:
        print("Error: no question provided", file=sys.stderr)
        sys.exit(1)

    store, embedder = _open_store(args.project)

    mode = "auto" if embedder else "lex"
    result = store.mem.ask(
        question,
        k=args.top_k,
        mode=mode,
        embedder=embedder,
    )

    print(json.dumps({
        "answer": result.get("answer", ""),
        "sources": len(result.get("hits", [])),
    }))


def cmd_audit(args: argparse.Namespace) -> None:
    """Audit previously researched topics. Optionally re-index or re-fetch."""
    from mcp_server.fetcher import DOCS_BASE, extract_library_name

    docs_dir = Path(DOCS_BASE)
    if not docs_dir.exists():
        print(json.dumps({"error": f"Docs directory not found: {docs_dir}"}))
        sys.exit(1)

    # Discover topics: each subdirectory with .md files is a topic
    topics: dict[str, dict] = {}
    skip_dirs = {"plans", "ios-development", "visionos-development"}
    for lib_dir in sorted(docs_dir.iterdir()):
        if not lib_dir.is_dir() or lib_dir.name.startswith("."):
            continue
        if lib_dir.name in skip_dirs:
            continue
        md_files = list(lib_dir.glob("**/*.md"))
        if md_files:
            total_bytes = sum(f.stat().st_size for f in md_files)
            topics[lib_dir.name] = {
                "files": len(md_files),
                "size_kb": round(total_bytes / 1024, 1),
                "path": str(lib_dir),
            }

    if not topics:
        print(json.dumps({"topics": [], "message": "No researched topics found"}))
        return

    # Filter to a specific topic if requested
    if args.topic:
        t = args.topic.lower()
        if t not in topics:
            print(json.dumps({"error": f"Topic '{t}' not found. Available: {list(topics.keys())}"}))
            sys.exit(1)
        topics = {t: topics[t]}

    # List mode (default)
    if not args.reindex and not args.refetch:
        rows = []
        for name, info in topics.items():
            rows.append({
                "topic": name,
                "files": info["files"],
                "size_kb": info["size_kb"],
            })
        print(json.dumps({"topics": rows, "count": len(rows)}, indent=2))
        return

    # Reindex mode: re-ingest existing local .md files into a fresh store
    if args.reindex:
        store, embedder = _open_store(args.project)

        total_ingested = 0
        results = []
        for name, info in topics.items():
            lib_dir = Path(info["path"])
            md_files = sorted(lib_dir.glob("**/*.md"))
            docs = []
            for md_file in md_files:
                text = md_file.read_text(encoding="utf-8", errors="replace")
                if not text.strip():
                    continue
                docs.append({
                    "title": md_file.stem,
                    "label": name,
                    "text": text,
                    "metadata": {"source": str(md_file)},
                })

            if docs:
                frame_ids = store.mem.put_many(docs, embedder=embedder)
                total_ingested += len(docs)
                results.append({
                    "topic": name,
                    "files": len(docs),
                    "frames": len(frame_ids),
                })

        store.close()
        print(json.dumps({
            "action": "reindex",
            "topics": len(results),
            "total_files": total_ingested,
            "results": results,
        }, indent=2))
        return

    # Refetch mode: re-fetch from source URLs and re-index
    if args.refetch:
        import asyncio
        from mcp_server.research import _resolve_doc_urls, KNOWN_DOCS
        from mcp_server.fetcher import fetch_url

        store, embedder = _open_store(args.project)

        async def _refetch_all():
            results = []
            for name in topics:
                urls = _resolve_doc_urls(name)
                fetched = 0
                failed = 0
                for url in urls:
                    try:
                        result = await fetch_url(url, force=True)
                        if result.get("content"):
                            store.mem.put_many([{
                                "title": url,
                                "label": extract_library_name(url),
                                "text": result["content"],
                                "metadata": result.get("meta") or {},
                            }], embedder=embedder)
                            fetched += 1
                            if not url.endswith("sitemap.xml"):
                                break  # got content from direct URL
                        else:
                            failed += 1
                    except Exception as exc:
                        log.warning("Fetch failed for %s: %s", url, exc)
                        failed += 1

                results.append({
                    "topic": name,
                    "fetched": fetched,
                    "failed": failed,
                })
            return results

        results = asyncio.run(_refetch_all())
        store.close()
        print(json.dumps({
            "action": "refetch",
            "results": results,
        }, indent=2))
        return


def cmd_status(args: argparse.Namespace) -> None:
    """Show knowledge store status."""
    h = args.project or _project_hash()
    store = get_store(h)
    path = store.path
    exists = os.path.exists(path)
    size = os.path.getsize(path) if exists else 0

    print(json.dumps({
        "path": path,
        "exists": exists,
        "size_kb": round(size / 1024, 1) if exists else 0,
        "project_hash": h,
    }))


def _add_project_arg(parser: argparse.ArgumentParser) -> None:
    """Add --project to a subparser."""
    parser.add_argument(
        "--project", default=None,
        help="Project hash override (defaults to cwd-based hash)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLI bridge to neo-research knowledge store"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = sub.add_parser("ingest", help="Ingest a single document")
    p_ingest.add_argument("--title", required=True, help="Document title")
    p_ingest.add_argument("--label", default="kb", help="Category label")
    p_ingest.add_argument("--text", default=None, help="Inline text (or pipe stdin)")
    _add_project_arg(p_ingest)
    p_ingest.set_defaults(func=cmd_ingest)

    # ingest-batch
    p_batch = sub.add_parser("ingest-batch", help="Batch ingest from JSONL stdin")
    _add_project_arg(p_batch)
    p_batch.set_defaults(func=cmd_ingest_batch)

    # search
    p_search = sub.add_parser("search", help="Search the knowledge store")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--top-k", type=int, default=10)
    _add_project_arg(p_search)
    p_search.set_defaults(func=cmd_search)

    # ask
    p_ask = sub.add_parser("ask", help="RAG Q&A over the store")
    p_ask.add_argument("question", nargs="?", default=None)
    p_ask.add_argument("--top-k", type=int, default=8)
    _add_project_arg(p_ask)
    p_ask.set_defaults(func=cmd_ask)

    # status
    p_status = sub.add_parser("status", help="Show store status")
    _add_project_arg(p_status)
    p_status.set_defaults(func=cmd_status)

    # audit
    p_audit = sub.add_parser("audit", help="Audit and re-process researched topics")
    p_audit.add_argument("--reindex", action="store_true",
                         help="Re-ingest local .md files into the knowledge store")
    p_audit.add_argument("--refetch", action="store_true",
                         help="Re-fetch from source URLs and re-index")
    p_audit.add_argument("--topic", default=None,
                         help="Limit to a single topic (default: all)")
    _add_project_arg(p_audit)
    p_audit.set_defaults(func=cmd_audit)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
