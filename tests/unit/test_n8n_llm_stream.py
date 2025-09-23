"""Unit tests for N8nLLMStream class"""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses
from livekit.agents.llm import ChatChunk, ChatMessage, ChoiceDelta, LLMStream

from n8n_agent import N8nLLMStream, N8nWebhookLLM


class TestN8nLLMStream:
    """Test suite for N8nLLMStream class"""

    @pytest.fixture
    def mock_llm(self, mock_webhook_url, mock_webhook_token):
        """Create a mock N8nWebhookLLM instance"""
        llm = N8nWebhookLLM(mock_webhook_url, mock_webhook_token)
        llm._cursors = {}
        return llm

    @pytest.fixture
    def sample_payload(self, mock_session_id):
        """Create a sample webhook payload"""
        return {
            "session_id": mock_session_id,
            "turn_id": "t_1",
            "input": {
                "type": "text",
                "text": "Test message"
            },
            "context": {},
            "idempotency_key": str(uuid.uuid4())
        }

    @pytest.mark.asyncio
    async def test_stream_init(self, mock_llm, mock_chat_context, mock_webhook_url, mock_webhook_token, sample_payload):
        """Test N8nLLMStream initialization"""
        stream = N8nLLMStream(
            llm=mock_llm,
            chat_ctx=mock_chat_context,
            fnc_ctx=None,
            webhook_url=mock_webhook_url,
            webhook_token=mock_webhook_token,
            payload=sample_payload,
            timeout=10.0
        )

        assert stream.webhook_url == mock_webhook_url
        assert stream.webhook_token == mock_webhook_token
        assert stream.payload == sample_payload
        assert stream.timeout == 10.0

    @pytest.mark.asyncio
    async def test_stream_context_manager(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test stream works as async context manager"""
        stream = N8nLLMStream(
            mock_llm, mock_chat_context, None,
            mock_webhook_url, "token", sample_payload, 5.0
        )

        # Mock the _run method to avoid actual webhook calls
        stream._run = AsyncMock()

        async with stream as s:
            assert s == stream

        # Verify cleanup happens
        assert stream._task is not None

    @pytest.mark.asyncio
    async def test_fetch_response_success(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test successful webhook response handling"""
        with aioresponses() as m:
            # Allow repeated calls to the same URL
            m.post(
                mock_webhook_url,
                payload={"output": "Test response from n8n"},
                status=200,
                repeat=True  # Allow multiple calls
            )

            stream = N8nLLMStream(
                mock_llm, mock_chat_context, None,
                mock_webhook_url, "", sample_payload, 5.0
            )

            await stream._fetch_response()

            # Check that cursor was set
            assert mock_chat_context in mock_llm._cursors
            cursor_msg = mock_llm._cursors[mock_chat_context]
            assert isinstance(cursor_msg, ChatMessage)
            assert cursor_msg.role == "assistant"
            assert cursor_msg.content == ["Test response from n8n"]

    @pytest.mark.asyncio
    async def test_fetch_response_complex_output(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test handling complex nested response structures"""
        with aioresponses() as m:
            m.post(
                mock_webhook_url,
                payload={"output": {"text": "Nested response"}},
                status=200,
                repeat=True
            )

            stream = N8nLLMStream(
                mock_llm, mock_chat_context, None,
                mock_webhook_url, "", sample_payload, 5.0
            )

            await stream._fetch_response()

            cursor_msg = mock_llm._cursors[mock_chat_context]
            assert cursor_msg.content == ["Nested response"]

    @pytest.mark.asyncio
    async def test_fetch_response_alternative_keys(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test response extraction with alternative key names"""
        with aioresponses() as m:
            # Test 'response' key
            m.post(
                mock_webhook_url,
                payload={"response": "Using response key"},
                status=200,
                repeat=True
            )

            stream = N8nLLMStream(
                mock_llm, mock_chat_context, None,
                mock_webhook_url, "", sample_payload, 5.0
            )

            await stream._fetch_response()

            cursor_msg = mock_llm._cursors[mock_chat_context]
            assert cursor_msg.content == ["Using response key"]

    @pytest.mark.asyncio
    async def test_fetch_response_with_auth_token(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test that auth token is included in headers"""
        with aioresponses() as m:
            def check_headers(url, **kwargs):
                headers = kwargs.get('headers', {})
                assert headers.get('Authorization') == 'Bearer test_token'
                return aiohttp.web.json_response({"output": "Authorized"})

            m.post(mock_webhook_url, callback=check_headers, repeat=True)

            stream = N8nLLMStream(
                mock_llm, mock_chat_context, None,
                mock_webhook_url, "test_token", sample_payload, 5.0
            )

            await stream._fetch_response()

    @pytest.mark.asyncio
    async def test_fetch_response_timeout(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test timeout handling"""
        with aioresponses() as m:
            # Simulate timeout by raising TimeoutError
            m.post(mock_webhook_url, exception=asyncio.TimeoutError(), repeat=True)

            stream = N8nLLMStream(
                mock_llm, mock_chat_context, None,
                mock_webhook_url, "", sample_payload, 1.0
            )

            await stream._fetch_response()

            cursor_msg = mock_llm._cursors[mock_chat_context]
            assert "timeout" in cursor_msg.content[0].lower() or "timed out" in cursor_msg.content[0].lower()

    @pytest.mark.asyncio
    async def test_fetch_response_error_status(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test handling of error HTTP status codes"""
        with aioresponses() as m:
            m.post(
                mock_webhook_url,
                payload={"error": "Internal server error"},
                status=500,
                repeat=True
            )

            stream = N8nLLMStream(
                mock_llm, mock_chat_context, None,
                mock_webhook_url, "", sample_payload, 5.0
            )

            await stream._fetch_response()

            cursor_msg = mock_llm._cursors[mock_chat_context]
            assert "trouble" in cursor_msg.content[0].lower()

    @pytest.mark.asyncio
    async def test_fetch_response_network_error(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test handling of network errors"""
        with aioresponses() as m:
            m.post(mock_webhook_url, exception=aiohttp.ClientError("Network error"), repeat=True)

            stream = N8nLLMStream(
                mock_llm, mock_chat_context, None,
                mock_webhook_url, "", sample_payload, 5.0
            )

            await stream._fetch_response()

            cursor_msg = mock_llm._cursors[mock_chat_context]
            assert "error" in cursor_msg.content[0].lower()

    @pytest.mark.asyncio
    async def test_chunking_mechanism(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test that response is properly chunked"""
        long_text = "A" * 150  # Create text longer than chunk size (50)

        with aioresponses() as m:
            # Only allow one call to avoid duplicates
            m.post(mock_webhook_url, payload={"output": long_text})

            # Track chunks sent to event channel
            chunks_sent = []

            # Create stream but DON'T let background task run
            with patch.object(LLMStream, '__init__', lambda self, *args, **kwargs: None):
                stream = N8nLLMStream.__new__(N8nLLMStream)
                stream._llm = mock_llm
                stream._chat_ctx = mock_chat_context
                stream.webhook_url = mock_webhook_url
                stream.webhook_token = ""
                stream.payload = sample_payload
                stream.timeout = 5.0

                # Create a mock event channel
                from livekit.agents.utils.aio import Chan
                stream._event_ch = Chan[ChatChunk](128)

                # Track chunks
                original_send = stream._event_ch.send_nowait

                def track_chunk(chunk):
                    chunks_sent.append(chunk)
                    original_send(chunk)

                stream._event_ch.send_nowait = track_chunk

                # Now call fetch_response directly
                await stream._fetch_response()

            # Should create 3 chunks (150 / 50)
            assert len(chunks_sent) == 3

            # Verify chunk structure
            for chunk in chunks_sent:
                assert isinstance(chunk, ChatChunk)
                assert chunk.delta is not None
                assert isinstance(chunk.delta, ChoiceDelta)

            # Reconstruct text from chunks
            reconstructed = "".join(c.delta.content for c in chunks_sent)
            assert reconstructed == long_text

    @pytest.mark.asyncio
    async def test_stream_iteration(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test async iteration over stream"""
        with aioresponses() as m:
            m.post(mock_webhook_url, payload={"output": "Short text"}, repeat=True)

            stream = N8nLLMStream(
                mock_llm, mock_chat_context, None,
                mock_webhook_url, "", sample_payload, 5.0
            )

            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            assert len(chunks) == 1
            assert chunks[0].delta.content == "Short text"

    @pytest.mark.asyncio
    async def test_empty_response_handling(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test handling of empty responses"""
        with aioresponses() as m:
            m.post(mock_webhook_url, payload={}, repeat=True)

            stream = N8nLLMStream(
                mock_llm, mock_chat_context, None,
                mock_webhook_url, "", sample_payload, 5.0
            )

            await stream._fetch_response()

            cursor_msg = mock_llm._cursors[mock_chat_context]
            assert cursor_msg.content == ["I couldn't generate a response."]

    @pytest.mark.asyncio
    async def test_run_method(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test the _run method delegates to _fetch_response"""
        stream = N8nLLMStream(
            mock_llm, mock_chat_context, None,
            mock_webhook_url, "", sample_payload, 5.0
        )

        stream._fetch_response = AsyncMock()

        await stream._run()

        stream._fetch_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_channel_close(self, mock_llm, mock_chat_context, mock_webhook_url, sample_payload):
        """Test that event channel is properly closed"""
        with aioresponses() as m:
            m.post(mock_webhook_url, payload={"output": "Test"}, repeat=True)

            stream = N8nLLMStream(
                mock_llm, mock_chat_context, None,
                mock_webhook_url, "", sample_payload, 5.0
            )

            # Mock the close method to track if it's called
            close_called = False
            original_close = stream._event_ch.close

            def track_close():
                nonlocal close_called
                close_called = True
                return original_close()

            stream._event_ch.close = track_close

            await stream._fetch_response()

            assert close_called