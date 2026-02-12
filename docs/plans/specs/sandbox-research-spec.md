---
name: sandbox-research
phase: 0
sprint: 1
parent: null
depends_on: []
status: draft
created: 2026-02-12
---

# Sandbox Infrastructure Research Spike

## Overview
Evaluate three integration paths between Anthropic's official sandbox infrastructure and the rlm-sandbox execution environment. Produce a recommendation that docker-sandbox spec will implement.

## Requirements
- [ ] REQ-1: Prototype srt-only path (IPython kernel as bare process wrapped with @anthropic-ai/sandbox-runtime)
- [ ] REQ-2: Prototype hybrid path (Docker container for kernel + srt wrapping the MCP server)
- [ ] REQ-3: Evaluate Docker Sandboxes path (entire stack in a Docker Sandbox microVM)
- [ ] REQ-4: Compare on: startup latency, resource isolation, security boundary strength, platform support, developer UX
- [ ] REQ-5: Document which path the docker-sandbox spec should follow

## Acceptance Criteria
- [ ] AC-1: srt-only prototype: IPython kernel starts inside srt, /exec works, filesystem restricted to /workspace
- [ ] AC-2: Hybrid prototype: Docker container runs kernel, MCP server wrapped with srt, both communicate
- [ ] AC-3: Docker Sandboxes feasibility check: can we nest our container inside a Docker Sandbox?
- [ ] AC-4: Comparison matrix with measured startup times and documented tradeoffs
- [ ] AC-5: Written recommendation in findings.md with rationale

## Technical Approach

### Path A: srt replaces Docker
- Install `@anthropic-ai/sandbox-runtime` globally
- Run IPython kernel as: `srt --settings srt-config.json python -m sandbox.repl`
- srt config: allowWrite=[./workspace], denyRead=[~/.ssh, ~/.aws], network blocked
- Test: can the kernel persist state, can the MCP server reach it via localhost
- Limitation to measure: no CPU/memory resource caps (srt doesn't do cgroups)

### Path B: Hybrid (srt + Docker)
- Keep docker-compose.yml with IPython kernel container (existing plan)
- Wrap MCP server: `srt --settings mcp-srt.json python mcp-server/server.py`
- srt config for MCP: allowWrite=[~/.rlm-sandbox], denyRead=[~/.ssh], allow localhost:8080
- Test: MCP server can reach Docker container but nothing else
- Benefit: defense-in-depth — even if MCP server is compromised, srt blocks exfiltration

### Path C: Docker Sandboxes target
- Run: `docker sandbox run rlm-sandbox ~/project`
- Inside the sandbox VM, our Docker container runs via the sandbox's private Docker daemon
- Test: can we build and start our container inside the sandbox?
- Check: does Docker-in-Docker work? Performance overhead?
- This path is more of a deployment target — doesn't change the core architecture

### Evaluation criteria
| Criterion | Weight | Notes |
|-----------|--------|-------|
| Startup latency | high | srt ~instant, Docker ~2-5s, Docker Sandbox ~10s |
| Isolation strength | high | srt=process-level, Docker=container, Sandbox=VM |
| Resource limits | medium | Docker has cgroups, srt doesn't, Sandbox has VM limits |
| Platform support | medium | srt=macOS+Linux, Docker=all, Sandbox=Docker Desktop |
| DX (debugging) | medium | srt=easiest (bare process), Docker=OK, Sandbox=hardest |
| Composability | low | How well does it play with Claude Code's native /sandbox |

## Files
| File | Action | Purpose |
|------|--------|---------|
| research/srt-prototype/ | create | srt-only prototype files |
| research/hybrid-prototype/ | create | srt+Docker hybrid prototype |
| research/comparison.md | create | Side-by-side evaluation matrix |
| docs/plans/findings.md | modify | Add recommendation to Research Findings |

## Tasks
1. Install and test @anthropic-ai/sandbox-runtime locally
2. Build srt-only prototype (IPython kernel wrapped with srt)
3. Build hybrid prototype (Docker kernel + srt-wrapped MCP server)
4. Test Docker Sandboxes feasibility (nested container check)
5. Write comparison matrix and recommendation

## Dependencies
- **Needs from:** nothing (research spike, runs first)
- **Provides to docker-sandbox:** architecture decision — which sandbox path to implement
- **Provides to mcp-server:** whether MCP server needs srt wrapping
- **Provides to claude-integration:** how /sandbox interacts with rlm.* tools

## Open Questions
- Does srt support Python processes that bind to localhost ports? (needed for srt-only path)
- Can srt's network proxy coexist with Docker's network? (needed for hybrid path)
- Does Docker Sandboxes' nested Docker daemon support docker-compose? (needed for Path C)
