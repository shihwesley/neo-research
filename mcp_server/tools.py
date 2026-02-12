"""MCP tool definitions for the sandbox."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from mcp.server.fastmcp import Context

from mcp_server.docker_manager import BASE_URL

if TYPE_CHECKING:
    from mcp_server.server import AppContext


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context


async def _post_exec(app: AppContext, code: str, timeout: int = 30) -> dict:
    """POST /exec to the sandbox container using the shared HTTP client."""
    await app.manager.ensure_running()
    r = await app.http.post(
        f"{BASE_URL}/exec",
        json={"code": code, "timeout": timeout},
        timeout=timeout + 5,
    )
    r.raise_for_status()
    return r.json()


def register_tools(mcp) -> None:
    """Register all sandbox tools on the MCP server instance."""

    @mcp.tool()
    async def rlm_exec(code: str, ctx: Context, timeout: int = 30) -> str:
        """Execute Python code in the sandbox and return output."""
        app = _ctx(ctx)
        data = await _post_exec(app, code, timeout)
        parts = []
        if data.get("output"):
            parts.append(data["output"])
        if data.get("stderr"):
            parts.append(f"[stderr] {data['stderr']}")
        return "\n".join(parts) if parts else "(no output)"

    # Paths the srt sandbox also blocks — defense-in-depth
    DENY_PATHS = [
        Path.home() / ".ssh",
        Path.home() / ".aws",
        Path.home() / ".config" / "gcloud",
        Path.home() / ".gnupg",
    ]

    @mcp.tool()
    async def rlm_load(path: str, var_name: str, ctx: Context) -> str:
        """Read a file from the host filesystem and inject it into the sandbox."""
        host_path = Path(path).expanduser().resolve()
        if any(host_path.is_relative_to(d) for d in DENY_PATHS):
            return f"Error: access denied — {host_path} is in a restricted directory"
        if not host_path.exists():
            return f"Error: file not found: {host_path}"
        content = host_path.read_text()
        escaped = json.dumps(content)
        code = f"{var_name} = {escaped}"
        app = _ctx(ctx)
        data = await _post_exec(app, code)
        if data.get("stderr"):
            return f"Error loading: {data['stderr']}"
        return f"Loaded {host_path.name} into `{var_name}` ({len(content)} chars)"

    @mcp.tool()
    async def rlm_get(name: str, ctx: Context, query: str | None = None) -> str:
        """Get a variable's value from the sandbox. Optionally run a query expression."""
        app = _ctx(ctx)
        await app.manager.ensure_running()

        if query:
            data = await _post_exec(app, query)
            output = data.get("output", "")
            if data.get("stderr"):
                output += f"\n[stderr] {data['stderr']}"
            return output or "(no output)"

        r = await app.http.get(f"{BASE_URL}/var/{name}", timeout=10)
        r.raise_for_status()
        data = r.json()

        if data.get("error"):
            return f"Error: {data['error']}"
        return json.dumps(data.get("value"), indent=2, default=str)

    @mcp.tool()
    async def rlm_vars(ctx: Context) -> str:
        """List all variables in the sandbox."""
        app = _ctx(ctx)
        await app.manager.ensure_running()
        r = await app.http.get(f"{BASE_URL}/vars", timeout=10)
        r.raise_for_status()
        var_list = r.json()

        if not var_list:
            return "(no variables)"
        lines = [f"  {v['name']}: {v['type']} = {v['summary']}" for v in var_list]
        return "\n".join(lines)

    @mcp.tool()
    async def rlm_sub_agent(
        signature: str,
        inputs: dict,
        ctx: Context,
        max_iterations: int = 10,
        max_llm_calls: int = 30,
    ) -> str:
        """Run a DSPy RLM sub-agent with the given signature and inputs."""
        from mcp_server.sub_agent import run_sub_agent

        app = _ctx(ctx)
        await app.manager.ensure_running()

        result = await run_sub_agent(
            signature=signature,
            inputs=inputs,
            max_iterations=max_iterations,
            max_llm_calls=max_llm_calls,
            sandbox_url=BASE_URL,
        )

        if result.get("error"):
            return f"Error: {result['error']}"

        # Store results in sandbox so they're accessible via rlm.get
        if result.get("result"):
            store_code = f"_sub_agent_result = {result['result']!r}"
            await _post_exec(app, store_code)

        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    async def rlm_reset(ctx: Context) -> str:
        """Reset the sandbox kernel, clearing all state."""
        app = _ctx(ctx)
        data = await _post_exec(app, "get_ipython().reset(new_session=True)")
        if data.get("stderr"):
            return f"Reset with warnings: {data['stderr']}"
        return "Sandbox reset."
