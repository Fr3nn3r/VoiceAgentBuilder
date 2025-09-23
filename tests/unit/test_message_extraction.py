"""Tests for message extraction from ChatContext"""
import pytest
from livekit.agents.llm import ChatContext, ChatMessage
from unittest.mock import MagicMock, patch

from n8n_agent import N8nWebhookLLM


class TestMessageExtraction:
    """Test message extraction logic from ChatContext"""

    def test_extract_simple_user_message(self, mock_webhook_url):
        """Test extraction of simple user message"""
        messages = [
            ChatMessage(role="user", content=["Hello, how are you?"])
        ]
        ctx = ChatContext(items=messages)

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)

            # Get the payload passed to stream
            call_args = mock_stream.call_args[0]
            payload = call_args[5]

            assert payload["input"]["text"] == "Hello, how are you?"

    def test_extract_latest_user_message(self, mock_webhook_url):
        """Test extraction of latest user message from conversation"""
        messages = [
            ChatMessage(role="user", content=["First message"]),
            ChatMessage(role="assistant", content=["Response"]),
            ChatMessage(role="user", content=["Second message"]),
            ChatMessage(role="assistant", content=["Another response"]),
            ChatMessage(role="user", content=["Latest message"]),
        ]
        ctx = ChatContext(items=messages)

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)

            call_args = mock_stream.call_args[0]
            payload = call_args[5]

            assert payload["input"]["text"] == "Latest message"

    def test_extract_from_empty_context(self, mock_webhook_url):
        """Test extraction from empty ChatContext"""
        ctx = ChatContext(items=[])

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)

            call_args = mock_stream.call_args[0]
            payload = call_args[5]

            assert payload["input"]["text"] == ""

    def test_extract_with_system_messages(self, mock_webhook_url):
        """Test extraction ignores system messages"""
        messages = [
            ChatMessage(role="system", content=["You are a helpful assistant"]),
            ChatMessage(role="user", content=["What is Python?"]),
            ChatMessage(role="system", content=["Be concise"]),
        ]
        ctx = ChatContext(items=messages)

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)

            call_args = mock_stream.call_args[0]
            payload = call_args[5]

            assert payload["input"]["text"] == "What is Python?"

    def test_extract_multipart_content(self, mock_webhook_url):
        """Test extraction from messages with multiple content parts"""
        messages = [
            ChatMessage(role="user", content=["Part 1", "Part 2", "Part 3"])
        ]
        ctx = ChatContext(items=messages)

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)

            call_args = mock_stream.call_args[0]
            payload = call_args[5]

            # Should get the first part
            assert payload["input"]["text"] == "Part 1"

    def test_extract_with_content_objects(self, mock_webhook_url):
        """Test extraction when content has object structure"""
        # For this test, we'll directly test the extraction logic
        # by mocking the ChatContext to return objects with text attributes
        ctx = MagicMock()

        # Create a mock message with content object
        mock_msg = MagicMock()
        mock_msg.role = "user"

        # Create a mock content object with text attribute
        content_obj = MagicMock()
        content_obj.text = "Content from object"
        mock_msg.content = [content_obj]

        # Mock the context to return our messages
        ctx.messages = [mock_msg]
        ctx.items = [mock_msg]

        # Make ctx iterable
        ctx.__iter__ = lambda self: iter([mock_msg])

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)

            call_args = mock_stream.call_args[0]
            payload = call_args[5]

            assert payload["input"]["text"] == "Content from object"

    def test_extract_mixed_content_types(self, mock_webhook_url):
        """Test extraction with mixed content types"""
        # Test with valid ChatMessage containing only strings
        # (since ChatMessage validates content types)
        messages = [
            ChatMessage(role="user", content=["String content", "Another string"])
        ]
        ctx = ChatContext(items=messages)

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)

            call_args = mock_stream.call_args[0]
            payload = call_args[5]

            # Should get the first string content
            assert payload["input"]["text"] == "String content"

    def test_extract_no_user_messages(self, mock_webhook_url):
        """Test extraction when there are no user messages"""
        messages = [
            ChatMessage(role="system", content=["System prompt"]),
            ChatMessage(role="assistant", content=["Assistant message"]),
        ]
        ctx = ChatContext(items=messages)

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)

            call_args = mock_stream.call_args[0]
            payload = call_args[5]

            assert payload["input"]["text"] == ""

    def test_extract_with_exception_handling(self, mock_webhook_url):
        """Test that extraction handles exceptions gracefully"""
        # Test that even with a completely broken context,
        # the code handles it gracefully and creates a stream with empty text
        ctx = object()  # Not a proper ChatContext at all

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)

            # Should still create stream with empty text
            call_args = mock_stream.call_args[0]
            payload = call_args[5]
            assert payload["input"]["text"] == ""

    def test_context_iteration_methods(self, mock_webhook_url):
        """Test different methods of accessing messages in ChatContext"""
        messages = [
            ChatMessage(role="user", content=["Test message"])
        ]

        # Test with messages property
        ctx = ChatContext(items=messages)
        llm = N8nWebhookLLM(mock_webhook_url, "")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)
            call_args = mock_stream.call_args[0]
            payload = call_args[5]
            assert payload["input"]["text"] == "Test message"

    def test_unicode_in_messages(self, mock_webhook_url):
        """Test extraction of unicode content"""
        messages = [
            ChatMessage(role="user", content=["Hello 世界 🌍"])
        ]
        ctx = ChatContext(items=messages)

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)

            call_args = mock_stream.call_args[0]
            payload = call_args[5]

            assert payload["input"]["text"] == "Hello 世界 🌍"

    def test_empty_content_in_message(self, mock_webhook_url):
        """Test handling of empty content in messages"""
        messages = [
            ChatMessage(role="user", content=[""]),
            ChatMessage(role="user", content=["Non-empty"])
        ]
        ctx = ChatContext(items=messages)

        llm = N8nWebhookLLM(mock_webhook_url, "")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)

            call_args = mock_stream.call_args[0]
            payload = call_args[5]

            # Should skip empty and get the non-empty message
            assert payload["input"]["text"] == "Non-empty"

    def test_payload_structure_completeness(self, mock_webhook_url):
        """Test that the complete payload structure is correct"""
        messages = [
            ChatMessage(role="user", content=["Test"])
        ]
        ctx = ChatContext(items=messages)

        llm = N8nWebhookLLM(mock_webhook_url, "token")

        with patch('n8n_agent.N8nLLMStream') as mock_stream:
            llm.chat(ctx)

            call_args = mock_stream.call_args[0]
            payload = call_args[5]

            # Check complete payload structure
            assert "session_id" in payload
            assert "turn_id" in payload
            assert "input" in payload
            assert "context" in payload
            assert "idempotency_key" in payload

            assert payload["input"]["type"] == "text"
            assert payload["input"]["text"] == "Test"
            assert payload["turn_id"] == "t_1"
            assert isinstance(payload["context"], dict)