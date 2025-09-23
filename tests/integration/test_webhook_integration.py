"""Integration tests for webhook communication and end-to-end flow"""
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioresponses import aioresponses
from livekit.agents.llm import ChatContext, ChatMessage

from n8n_agent import N8nWebhookLLM


class TestWebhookIntegration:
    """Integration tests for webhook communication"""

    @pytest.mark.asyncio
    async def test_full_chat_flow(self, mock_webhook_url):
        """Test complete flow from chat input to response"""
        messages = [
            ChatMessage(role="user", content=["What is Python?"])
        ]
        chat_ctx = ChatContext(items=messages)

        with aioresponses() as m:
            m.post(
                mock_webhook_url,
                payload={"output": "Python is a programming language"},
                status=200
            )

            llm = N8nWebhookLLM(mock_webhook_url, "token")
            stream = llm.chat(chat_ctx)

            # Collect all chunks
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            # Verify we got chunks
            assert len(chunks) > 0

            # Reconstruct response
            full_response = "".join(c.delta.content for c in chunks if c.delta)
            assert full_response == "Python is a programming language"

    @pytest.mark.asyncio
    async def test_multiple_turns_conversation(self, mock_webhook_url):
        """Test multiple conversation turns"""
        llm = N8nWebhookLLM(mock_webhook_url, "token")

        # First turn
        messages1 = [ChatMessage(role="user", content=["Hello"])]
        ctx1 = ChatContext(items=messages1)

        with aioresponses() as m:
            m.post(mock_webhook_url, payload={"output": "Hi there!"})

            stream1 = llm.chat(ctx1)
            chunks1 = [chunk async for chunk in stream1]

        assert llm.turn_counter == 1
        response1 = "".join(c.delta.content for c in chunks1 if c.delta)
        assert response1 == "Hi there!"

        # Second turn
        messages2 = [
            ChatMessage(role="user", content=["Hello"]),
            ChatMessage(role="assistant", content=["Hi there!"]),
            ChatMessage(role="user", content=["How are you?"])
        ]
        ctx2 = ChatContext(items=messages2)

        with aioresponses() as m:
            m.post(mock_webhook_url, payload={"output": "I'm doing great!"})

            stream2 = llm.chat(ctx2)
            chunks2 = [chunk async for chunk in stream2]

        assert llm.turn_counter == 2
        response2 = "".join(c.delta.content for c in chunks2 if c.delta)
        assert response2 == "I'm doing great!"

    @pytest.mark.asyncio
    async def test_session_consistency(self, mock_webhook_url):
        """Test that session ID remains consistent across turns"""
        llm = N8nWebhookLLM(mock_webhook_url, "token")
        initial_session_id = llm.session_id

        payloads_sent = []

        def capture_payload(url, **kwargs):
            payloads_sent.append(kwargs.get('json'))
            return aiohttp.web.json_response({"output": "Response"})

        with aioresponses() as m:
            m.post(mock_webhook_url, callback=capture_payload)

            # Multiple turns
            for i in range(3):
                ctx = ChatContext(items=[
                    ChatMessage(role="user", content=[f"Message {i}"])
                ])
                stream = llm.chat(ctx)
                async for _ in stream:
                    pass

        # Verify session ID consistency
        assert len(payloads_sent) == 3
        for payload in payloads_sent:
            assert payload["session_id"] == initial_session_id

        # Verify turn IDs increment
        assert payloads_sent[0]["turn_id"] == "t_1"
        assert payloads_sent[1]["turn_id"] == "t_2"
        assert payloads_sent[2]["turn_id"] == "t_3"

    @pytest.mark.asyncio
    async def test_payload_structure(self, mock_webhook_url):
        """Test that webhook payload has correct structure"""
        captured_payload = None

        def capture_payload(url, **kwargs):
            nonlocal captured_payload
            captured_payload = kwargs.get('json')
            return aiohttp.web.json_response({"output": "Test"})

        with aioresponses() as m:
            m.post(mock_webhook_url, callback=capture_payload)

            llm = N8nWebhookLLM(mock_webhook_url, "")
            ctx = ChatContext(items=[
                ChatMessage(role="user", content=["Test message"])
            ])

            stream = llm.chat(ctx)
            async for _ in stream:
                pass

        # Verify payload structure
        assert captured_payload is not None
        assert "session_id" in captured_payload
        assert "turn_id" in captured_payload
        assert "input" in captured_payload
        assert "context" in captured_payload
        assert "idempotency_key" in captured_payload

        # Verify input structure
        assert captured_payload["input"]["type"] == "text"
        assert captured_payload["input"]["text"] == "Test message"

        # Verify idempotency key is valid UUID
        uuid.UUID(captured_payload["idempotency_key"])

    @pytest.mark.asyncio
    async def test_concurrent_streams(self, mock_webhook_url):
        """Test handling multiple concurrent streams"""
        llm = N8nWebhookLLM(mock_webhook_url, "token")

        async def make_request(message):
            ctx = ChatContext(items=[
                ChatMessage(role="user", content=[message])
            ])
            stream = llm.chat(ctx)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)
            return chunks

        with aioresponses() as m:
            # Setup multiple responses
            for i in range(3):
                m.post(mock_webhook_url, payload={"output": f"Response {i}"})

            # Make concurrent requests
            results = await asyncio.gather(
                make_request("Message 1"),
                make_request("Message 2"),
                make_request("Message 3")
            )

        assert len(results) == 3
        for i, chunks in enumerate(results):
            assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_response_formats(self, mock_webhook_url):
        """Test handling various response formats from n8n"""
        test_cases = [
            # Simple string in output
            ({"output": "Simple response"}, "Simple response"),
            # Nested object with text
            ({"output": {"text": "Nested text"}}, "Nested text"),
            # Using response key
            ({"response": "Response key"}, "Response key"),
            # Using text key
            ({"text": "Text key"}, "Text key"),
            # Using message key
            ({"message": "Message key"}, "Message key"),
            # String response
            ("Plain string", "Plain string"),
            # Empty response
            ({}, "I couldn't generate a response."),
        ]

        llm = N8nWebhookLLM(mock_webhook_url, "")

        for response_data, expected_text in test_cases:
            with aioresponses() as m:
                if isinstance(response_data, str):
                    m.post(mock_webhook_url, body=response_data, content_type='text/plain')
                else:
                    m.post(mock_webhook_url, payload=response_data)

                ctx = ChatContext(items=[
                    ChatMessage(role="user", content=["Test"])
                ])

                stream = llm.chat(ctx)
                chunks = []
                async for chunk in stream:
                    chunks.append(chunk)

                result = "".join(c.delta.content for c in chunks if c.delta)
                assert result == expected_text

    @pytest.mark.asyncio
    async def test_auth_header_included(self, mock_webhook_url):
        """Test that authentication header is properly included"""
        headers_captured = None

        def capture_headers(url, **kwargs):
            nonlocal headers_captured
            headers_captured = kwargs.get('headers', {})
            return aiohttp.web.json_response({"output": "Authenticated"})

        with aioresponses() as m:
            m.post(mock_webhook_url, callback=capture_headers)

            llm = N8nWebhookLLM(mock_webhook_url, "secret_token_123")
            ctx = ChatContext(items=[
                ChatMessage(role="user", content=["Test"])
            ])

            stream = llm.chat(ctx)
            async for _ in stream:
                pass

        assert headers_captured is not None
        assert headers_captured.get("Authorization") == "Bearer secret_token_123"
        assert headers_captured.get("Content-Type") == "application/json"

    @pytest.mark.asyncio
    async def test_empty_token_no_auth_header(self, mock_webhook_url):
        """Test that no auth header is sent when token is empty"""
        headers_captured = None

        def capture_headers(url, **kwargs):
            nonlocal headers_captured
            headers_captured = kwargs.get('headers', {})
            return aiohttp.web.json_response({"output": "No auth"})

        with aioresponses() as m:
            m.post(mock_webhook_url, callback=capture_headers)

            llm = N8nWebhookLLM(mock_webhook_url, "")
            ctx = ChatContext(items=[
                ChatMessage(role="user", content=["Test"])
            ])

            stream = llm.chat(ctx)
            async for _ in stream:
                pass

        assert headers_captured is not None
        assert "Authorization" not in headers_captured