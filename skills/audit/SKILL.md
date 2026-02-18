---
name: audit
description: "Audit previously researched topics and optionally re-index them through the current pipeline. Use when the research flow has changed and you want to backfill, or to see what's been researched."
---

# Knowledge Audit

Re-process previously researched topics through the updated pipeline.

## When This Skill Triggers

- "audit my research", "what have I researched?", "re-index everything"
- After updating the research pipeline and wanting to backfill old topics
- "reindex", "backfill", "re-run research on old topics"
- `/neo-research:audit` explicitly

## Step 1: List What's Been Researched

Call the MCP tool to see all topics:

```
rlm_knowledge_audit()
```

This scans `.claude/docs/` for library directories and reports file counts and sizes. Review the list with the user before re-indexing.

## Step 2: Re-index (if requested)

If the user wants to re-process topics through the current pipeline:

```
rlm_knowledge_audit(reindex=True)
```

To limit to a single topic:

```
rlm_knowledge_audit(reindex=True, topic="fastapi")
```

This reads existing .md files from disk and re-ingests them into the knowledge store. No network calls — fast and offline.

## Step 3: Re-fetch (CLI only)

For a full re-fetch from source URLs (network required), use the CLI:

```bash
HOME_DIR=$(echo ~)
KNOWLEDGE_CLI=$(ls -d $HOME_DIR/.claude/plugins/cache/shihwesley-plugins/neo-research/*/scripts/knowledge-cli.py 2>/dev/null | sort -V | tail -1)
python3 "$KNOWLEDGE_CLI" audit --refetch
```

Or limit to one topic:

```bash
python3 "$KNOWLEDGE_CLI" audit --refetch --topic fastapi
```

## Rules

- Always show the topic list first before re-indexing. Let the user confirm.
- `--reindex` is fast (local files only). Recommend this after pipeline changes.
- `--refetch` hits the network. Recommend this when upstream docs have changed.
- Report results: how many topics, files, and frames were processed.
