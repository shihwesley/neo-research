"""Tests for mcp_server/llm_callback.py — LLMCallbackServer."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from mcp_server.llm_callback import CALLBACK_PORT, DEFAULT_SUB_LM, LLMCallbackServer


class TestLLMCallbackServerProperties:
    def test_default_port(self):
        server = LLMCallbackServer()
        assert server.port == CALLBACK_PORT

    def test_callback_url(self):
        server = LLMCallbackServer(port=9999)
        assert server.callback_url == "http://host.docker.internal:9999/llm_query"

    def test_callback_url_local(self):
        server = LLMCallbackServer(port=9999)
        assert server.callback_url_local == "http://127.0.0.1:9999/llm_query"

    def test_default_model(self):
        server = LLMCallbackServer()
        assert server.model == DEFAULT_SUB_LM


class TestLLMCallbackServerLifecycle:
    @pytest.mark.anyio
    async def test_start_and_stop(self):
        # Use a high port to avoid conflicts
        server = LLMCallbackServer(port=18081)
        await server.start()
        assert server._server is not None
        await server.stop()
        assert server._server is None

    @pytest.mark.anyio
    async def test_stop_without_start(self):
        server = LLMCallbackServer(port=18082)
        # should not raise
        await server.stop()


class TestLLMCallbackServerHTTP:
    """Test the actual HTTP handling by sending raw TCP requests."""

    @pytest.mark.anyio
    async def test_post_llm_query_returns_result(self):
        server = LLMCallbackServer(port=18083)

        # Mock the sub_lm property to avoid real API calls
        mock_lm = MagicMock(return_value=["mocked response"])
        server._sub_lm = mock_lm

        await server.start()
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", 18083)
            body = json.dumps({"prompt": "hello"}).encode()
            request = (
                f"POST /llm_query HTTP/1.1\r\n"
                f"Host: 127.0.0.1\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"\r\n"
            ).encode() + body

            writer.write(request)
            await writer.drain()

            response = await asyncio.wait_for(reader.read(4096), timeout=10)
            writer.close()

            response_text = response.decode()
            # Parse status line
            status_line = response_text.split("\r\n")[0]
            assert "200" in status_line

            # Parse body (after double CRLF)
            resp_body = response_text.split("\r\n\r\n", 1)[1]
            data = json.loads(resp_body)
            assert data["result"] == "mocked response"

        finally:
            await server.stop()

    @pytest.mark.anyio
    async def test_wrong_path_returns_404(self):
        server = LLMCallbackServer(port=18084)
        await server.start()
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", 18084)
            request = (
                "GET /wrong HTTP/1.1\r\n"
                "Host: 127.0.0.1\r\n"
                "\r\n"
            ).encode()

            writer.write(request)
            await writer.drain()

            response = await asyncio.wait_for(reader.read(4096), timeout=5)
            writer.close()

            assert b"404" in response

        finally:
            await server.stop()

    @pytest.mark.anyio
    async def test_missing_prompt_returns_400(self):
        server = LLMCallbackServer(port=18085)
        await server.start()
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", 18085)
            body = json.dumps({"prompt": ""}).encode()
            request = (
                f"POST /llm_query HTTP/1.1\r\n"
                f"Host: 127.0.0.1\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"\r\n"
            ).encode() + body

            writer.write(request)
            await writer.drain()

            response = await asyncio.wait_for(reader.read(4096), timeout=5)
            writer.close()

            assert b"400" in response

        finally:
            await server.stop()

    @pytest.mark.anyio
    async def test_lm_error_returns_500(self):
        server = LLMCallbackServer(port=18086)
        mock_lm = MagicMock(side_effect=RuntimeError("API error"))
        server._sub_lm = mock_lm

        await server.start()
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", 18086)
            body = json.dumps({"prompt": "will fail"}).encode()
            request = (
                f"POST /llm_query HTTP/1.1\r\n"
                f"Host: 127.0.0.1\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"\r\n"
            ).encode() + body

            writer.write(request)
            await writer.drain()

            response = await asyncio.wait_for(reader.read(4096), timeout=5)
            writer.close()

            assert b"500" in response

        finally:
            await server.stop()


class TestQueryLM:
    @pytest.mark.anyio
    async def test_returns_first_from_list(self):
        server = LLMCallbackServer(port=18087)
        mock_lm = MagicMock(return_value=["first", "second"])
        server._sub_lm = mock_lm
        result = await server._query_lm("test prompt")
        assert result == "first"
        mock_lm.assert_called_once_with("test prompt")

    @pytest.mark.anyio
    async def test_stringifies_non_list(self):
        server = LLMCallbackServer(port=18088)
        mock_lm = MagicMock(return_value=42)
        server._sub_lm = mock_lm
        result = await server._query_lm("test")
        assert result == "42"
