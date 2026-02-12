# Sandbox Path Comparison

## Prototypes Built
- **Path A (srt-only):** IPython kernel as bare Python process, wrapped with `srt`. 15/15 tests pass.
- **Path B (hybrid):** IPython kernel in Docker container, MCP server wrapped with `srt`. 7/7 tests pass.
- **Path C (Docker Sandboxes):** Not testable — `docker sandbox` command unavailable in Docker Desktop 28.0.1.

## Measured Data

| Criterion | Path A: srt-only | Path B: Hybrid | Path C: Docker Sandboxes |
|-----------|------------------|----------------|--------------------------|
| **Startup latency** | ~200ms | ~4s (cold), ~1s (warm) | ~10s (estimated, untested) |
| **Filesystem isolation** | srt seatbelt (denyRead, allowWrite) | Docker + srt (double layer) | VM-level |
| **Network isolation** | srt proxy (domain filtering) | Docker (--dns 0.0.0.0) + srt proxy | VM-level |
| **Resource limits (CPU/mem)** | None (srt doesn't do cgroups) | Docker cgroups (--memory, --cpus) | VM limits |
| **Platform support** | macOS + Linux (srt-native) | macOS + Linux + Windows (Docker) | Docker Desktop only |
| **Docker dependency** | None | Yes | Yes (specific version) |
| **DX (debugging)** | Best (bare process, standard Python) | Good (docker logs, exec) | Worst (VM inside VM) |
| **Composability w/ /sandbox** | Works (different processes) | Works (different processes) | Redundant (VM already isolates) |
| **Security depth** | Single layer (srt) | Double layer (Docker + srt) | Triple layer (VM + Docker + srt) |

## Key Findings

### srt-only (Path A)
- Port binding works with `allowLocalBinding: true`
- Host can connect to srt-sandboxed process on localhost (critical for MCP → kernel)
- No network egress (proxy blocks all non-allowed domains)
- File read/write restrictions work correctly on macOS seatbelt
- **Gap:** No resource limits. A `while True: pass` consumes all host CPU.
- **Gap:** Process management is on us (no container restart, no healthcheck daemon)

### Hybrid (Path B)
- `--network=none` breaks port mapping (found during testing)
- Fix: `--dns 0.0.0.0` on bridge network — container can't resolve hostnames but port mapping works
- Alternative: Unix socket on mounted volume (no network needed at all)
- srt successfully wraps host process while Docker isolates kernel
- Docker provides cgroups for CPU/memory caps
- **Gap:** More moving parts (Docker daemon + srt + container + host process)
- **Gap:** Docker must be running

### Docker Sandboxes (Path C)
- `docker sandbox` not available in Docker Desktop 28.0.1
- Would require upgrading to a version with Sandboxes support
- Architecturally: our Docker container would run inside the Sandbox's private Docker daemon
- Docker-in-Docker adds latency and complexity
- This is more of a deployment concern than an architecture decision

## docker-sandbox Spec Impact

### --network=none reconsideration
The original spec says `--network=none`. This breaks port mapping, which the MCP server needs.
Options (ordered by preference):
1. **Bridge + --dns 0.0.0.0:** Port mapping works, DNS fails, direct IP access still possible but no hostname resolution. Quick, simple.
2. **Unix socket on volume:** No network at all. Host writes to socket, container reads. Strongest isolation but needs socket-based server instead of HTTP.
3. **Custom bridge with iptables:** Most control but OS-specific and complex.

Recommendation: Option 1 for v1, option 2 as a future hardening step.

## Recommendation

**Path B (Hybrid) for production. Path A (srt-only) as a lightweight fallback.**

Rationale:
- Hybrid gives the strongest isolation (Docker cgroups + srt network/filesystem)
- srt-only is the fastest and simplest — good for development, demos, and users without Docker
- Docker Sandboxes is a deployment concern, not an architecture choice — support it later as a deployment target

Implementation plan:
1. Build the docker-sandbox spec as designed (Docker container with IPython kernel)
2. Fix `--network=none` → `--dns 0.0.0.0` on bridge (or Unix socket)
3. Add srt wrapping to mcp-server spec (MCP server runs inside srt)
4. Add a `--no-docker` flag to MCP server that falls back to srt-only mode (Path A)
5. Document Docker Sandboxes as a deployment option in claude-integration spec

This gives users three tiers:
- **Tier 1 (no Docker):** srt-only, ~200ms startup, process-level isolation
- **Tier 2 (Docker):** hybrid, ~4s startup, container + srt isolation
- **Tier 3 (Docker Sandboxes):** full VM isolation, deployment target for untrusted environments
