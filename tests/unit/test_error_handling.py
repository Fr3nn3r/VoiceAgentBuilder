"""Tests for error handling and edge cases"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses
from livekit.agents.llm import ChatContext, ChatMessage

from n8n_agent import N8nLLMStream, N8nWebhookLLM


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_webhook_url):
        """Test proper timeout handling"""
        llm = N8nWebhookLLM(mock_webhook_url, "", timeout=0.1)

        with aioresponses() as m:
            # Simulate timeout
            m.post(mock_webhook_url, exception=aiohttp.ClientTimeout())

            ctx = ChatContext(items=[
                ChatMessage(role="user", content=["Test"])
            ])

            stream = llm.chat(ctx)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            result = "".join(c.delta.content for c in chunks if c.delta)
            assert "timeout" in result.lower() or "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_network_error(self, mock_webhook_url):
        """Test handling of network errors"""
        llm = N8nWebhookLLM(mock_webhook_url, "")

        with aioresponses() as m:
            m.post(mock_webhook_url, exception=aiohttp.ClientError("Connection failed"))

            ctx = ChatContext(items=[
                ChatMessage(role="user", content=["Test"])
            ])

            stream = llm.chat(ctx)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            result = "".join(c.delta.content for c in chunks if c.delta)
            assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, mock_webhook_url):
        """Test handling of invalid JSON responses"""
        llm = N8nWebhookLLM(mock_webhook_url, "")

        with aioresponses() as m:
            m.post(mock_webhook_url, body="Not valid JSON", content_type='text/plain')

            ctx = ChatContext(items=[
                ChatMessage(role="user", content=["Test"])
            ])

            stream = llm.chat(ctx)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            # Should handle gracefully and return the plain text
            result = "".join(c.delta.content for c in chunks if c.delta)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_http_error_codes(self, mock_webhook_url):
        """Test handling of various HTTP error codes"""
        error_codes = [400, 401, 403, 404, 500, 502, 503]

        llm = N8nWebhookLLM(mock_webhook_url, "")

        for code in error_codes:
            with aioresponses() as m:
                m.post(mock_webhook_url, status=code, body=f"Error {code}")

                ctx = ChatContext(items=[
                    ChatMessage(role="user", content=["Test"])
                ])

                stream = llm.chat(ctx)
                chunks = []
                async for chunk in stream:
                    chunks.append(chunk)

                result = "".join(c.delta.content for c in chunks if c.delta)
                assert "trouble" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_response_body(self, mock_webhook_url):
        """Test handling of empty response body"""
        llm = N8nWebhookLLM(mock_webhook_url, "")

        with aioresponses() as m:
            m.post(mock_webhook_url, payload={})

            ctx = ChatContext(items=[
                ChatMessage(role="user", content=["Test"])
            ])

            stream = llm.chat(ctx)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            result = "".join(c.delta.content for c in chunks if c.delta)
            assert result == "I couldn't generate a response."

    @pytest.mark.asyncio
    async def test_null_values_in_response(self, mock_webhook_url):
        """Test handling of null values in response"""
        llm = N8nWebhookLLM(mock_webhook_url, "")

        test_cases = [
            {"output": None},
            {"response": None, "text": None},
            {"output": {"text": None}},
        ]

        for response_data in test_cases:
            with aioresponses() as m:
                m.post(mock_webhook_url, payload=response_data)

                ctx = ChatContext(items=[
                    ChatMessage(role="user", content=["Test"])
                ])

                stream = llm.chat(ctx)
                chunks = []
                async for chunk in stream:
                    chunks.append(chunk)

                result = "".join(c.delta.content for c in chunks if c.delta)
                assert result == "I couldn't generate a response."

    @pytest.mark.asyncio
    async def test_very_long_response(self, mock_webhook_url):
        """Test handling of very long responses"""
        # Create a very long text (10000 characters)
        long_text = "A" * 10000

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with aioresponses() as m:
            m.post(mock_webhook_url, payload={"output": long_text})

            ctx = ChatContext(items=[
                ChatMessage(role="user", content=["Test"])
            ])

            stream = llm.chat(ctx)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            # Verify chunking worked correctly
            assert len(chunks) == 200  # 10000 / 50 (chunk size)

            # Verify full text is preserved
            result = "".join(c.delta.content for c in chunks if c.delta)
            assert result == long_text

    @pytest.mark.asyncio
    async def test_unicode_handling(self, mock_webhook_url):
        """Test handling of unicode characters"""
        unicode_text = "Hello 世界 🌍 Привет مرحبا"

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with aioresponses() as m:
            m.post(mock_webhook_url, payload={"output": unicode_text})

            ctx = ChatContext(items=[
                ChatMessage(role="user", content=["Test"])
            ])

            stream = llm.chat(ctx)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            result = "".join(c.delta.content for c in chunks if c.delta)
            assert result == unicode_text

    @pytest.mark.asyncio
    async def test_special_characters_in_response(self, mock_webhook_url):
        """Test handling of special characters"""
        special_text = 'Special chars: \n\t"quotes" \'single\' <tags> & symbols'

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with aioresponses() as m:
            m.post(mock_webhook_url, payload={"output": special_text})

            ctx = ChatContext(items=[
                ChatMessage(role="user", content=["Test"])
            ])

            stream = llm.chat(ctx)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            result = "".join(c.delta.content for c in chunks if c.delta)
            assert result == special_text

    @pytest.mark.asyncio
    async def test_connection_pool_error(self, mock_webhook_url):
        """Test handling of connection pool errors"""
        llm = N8nWebhookLLM(mock_webhook_url, "")

        with aioresponses() as m:
            m.post(mock_webhook_url, exception=aiohttp.ClientConnectionError("Connection pool error"))

            ctx = ChatContext(items=[
                ChatMessage(role="user", content=["Test"])
            ])

            stream = llm.chat(ctx)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            result = "".join(c.delta.content for c in chunks if c.delta)
            assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_redirect_handling(self, mock_webhook_url):
        """Test that redirects are not automatically followed (security)"""
        redirect_url = "https://evil.com/webhook"

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with aioresponses() as m:
            # Setup redirect
            m.post(mock_webhook_url, status=302, headers={"Location": redirect_url})
            m.post(redirect_url, payload={"output": "Should not reach here"})

            ctx = ChatContext(items=[
                ChatMessage(role="user", content=["Test"])
            ])

            stream = llm.chat(ctx)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            # Should treat redirect as error
            result = "".join(c.delta.content for c in chunks if c.delta)
            assert "trouble" in result.lower() or "error" in result.lower()