"""Host-side callback server for llm_query() calls from the sandbox.

Runs a minimal asyncio HTTP server on CALLBACK_PORT. When sandbox code calls
llm_query(prompt), the injected stub POSTs here, and we route through dspy.LM
(Haiku 4.5) on the host side. API keys never enter the container.
"""

from __future__ import annotations

import asyncio
import json
import logging

import dspy

log = logging.getLogger(__name__)

DEFAULT_SUB_LM = "anthropic/claude-haiku-4-5-20251001"
CALLBACK_PORT = 8081


class LLMCallbackServer:
    """Async HTTP server that handles llm_query() callbacks from the sandbox."""

    def __init__(self, port: int = CALLBACK_PORT, model: str = DEFAULT_SUB_LM):
        self.port = port
        self.model = model
        self._sub_lm: dspy.LM | None = None
        self._server: asyncio.Server | None = None

    @property
    def callback_url(self) -> str:
        """URL the sandbox stub should POST to."""
        return f"http://host.docker.internal:{self.port}/llm_query"

    @property
    def callback_url_local(self) -> str:
        """URL for bare-process mode (no Docker, everything on localhost)."""
        return f"http://127.0.0.1:{self.port}/llm_query"

    @property
    def sub_lm(self) -> dspy.LM:
        if self._sub_lm is None:
            self._sub_lm = dspy.LM(self.model)
        return self._sub_lm

    async def start(self) -> None:
        """Start listening for llm_query callbacks."""
        self._server = await asyncio.start_server(
            self._handle_connection, "0.0.0.0", self.port
        )
        log.info("LLM callback server listening on port %d", self.port)

    async def stop(self) -> None:
        """Shut down the callback server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            log.info("LLM callback server stopped")

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a single HTTP connection from the sandbox stub."""
        try:
            # Read request line
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            if not request_line:
                return

            method, path, _ = request_line.decode().strip().split(" ", 2)

            # Read headers
            content_length = 0
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5)
                decoded = line.decode().strip()
                if not decoded:
                    break
                if decoded.lower().startswith("content-length:"):
                    content_length = int(decoded.split(":", 1)[1].strip())

            # Only accept POST /llm_query
            if method != "POST" or path != "/llm_query":
                self._send_response(writer, 404, {"error": "not found"})
                return

            # Read body
            body = b""
            if content_length > 0:
                body = await asyncio.wait_for(
                    reader.readexactly(content_length), timeout=5
                )

            data = json.loads(body)
            prompt = data.get("prompt", "")

            if not prompt:
                self._send_response(writer, 400, {"error": "missing prompt"})
                return

            # Route to host-side LM
            result = await self._query_lm(prompt)
            self._send_response(writer, 200, {"result": result})

        except asyncio.TimeoutError:
            log.warning("Callback connection timed out")
            self._send_response(writer, 408, {"error": "timeout"})
        except Exception:
            log.exception("Error handling llm_query callback")
            self._send_response(writer, 500, {"error": "internal error"})
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _query_lm(self, prompt: str) -> str:
        """Run the prompt through dspy.LM in a thread (it's sync)."""
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, self.sub_lm, prompt)
        # dspy.LM returns a list of completions
        if isinstance(response, list) and response:
            return response[0]
        return str(response)

    @staticmethod
    def _send_response(
        writer: asyncio.StreamWriter, status: int, body: dict
    ) -> None:
        """Write a minimal HTTP/1.1 JSON response."""
        payload = json.dumps(body).encode()
        reason = {200: "OK", 400: "Bad Request", 404: "Not Found",
                  408: "Timeout", 500: "Internal Server Error"}.get(status, "Error")
        header = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        writer.write(header.encode() + payload)
