# Changelog

## 1.0.0 - 2026-02-13

### Added
- Plugin distribution structure (.claude-plugin, .mcp.json, agents, skills, hooks)
- Knowledge store: memvid-sdk backed hybrid search (.mv2 files)
  - `rlm_search`, `rlm_ask`, `rlm_timeline`, `rlm_ingest` tools
- Doc fetcher: URL fetching with .md variant detection, sitemap support, dual storage
  - `rlm_fetch`, `rlm_load_dir`, `rlm_fetch_sitemap` tools
- Research automation: compound research tool + knowledge management
  - `rlm_research`, `rlm_knowledge_status`, `rlm_knowledge_clear` tools
- Custom agents: `rlm-researcher` (doc research) and `rlm-sandbox` (code execution)
- Skills: `/rlm-sandbox:research` and `/rlm-sandbox:knowledge-status`
- Context7 routing hook (indexes Context7 fetches into knowledge store)
- Auto-setup script (venv + deps on first run)

### Core (from pre-plugin development)
- Docker sandbox with FastAPI + IPython kernel
- DSPy sub-agent support (host-side, Haiku 4.5)
- Session persistence via dill
- Three isolation tiers (process, Docker container, Docker Sandboxes)
- 209 tests
