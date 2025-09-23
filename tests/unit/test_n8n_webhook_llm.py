"""Unit tests for N8nWebhookLLM class"""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from n8n_agent import N8nWebhookLLM


class TestN8nWebhookLLM:
    """Test suite for N8nWebhookLLM class"""

    def test_init(self, mock_webhook_url, mock_webhook_token):
        """Test N8nWebhookLLM initialization"""
        llm = N8nWebhookLLM(
            webhook_url=mock_webhook_url,
            webhook_token=mock_webhook_token,
            timeout=10.0
        )

        assert llm.webhook_url == mock_webhook_url
        assert llm.webhook_token == mock_webhook_token
        assert llm.timeout == 10.0
        assert llm.turn_counter == 0
        assert isinstance(llm.session_id, str)
        assert llm._cursors == {}

    def test_init_default_timeout(self, mock_webhook_url):
        """Test initialization with default timeout"""
        llm = N8nWebhookLLM(
            webhook_url=mock_webhook_url,
            webhook_token=""
        )

        assert llm.timeout == 8.0
        assert llm.webhook_token == ""

    def test_session_id_generation(self, mock_webhook_url):
        """Test that each instance gets a unique session ID"""
        llm1 = N8nWebhookLLM(mock_webhook_url, "")
        llm2 = N8nWebhookLLM(mock_webhook_url, "")

        assert llm1.session_id != llm2.session_id
        # Verify they're valid UUIDs
        uuid.UUID(llm1.session_id)
        uuid.UUID(llm2.session_id)

    @patch('n8n_agent.N8nLLMStream')
    def test_chat_creates_stream(self, mock_stream_class, mock_webhook_url, mock_chat_context):
        """Test that chat() creates and returns an N8nLLMStream"""
        llm = N8nWebhookLLM(mock_webhook_url, "token")
        mock_stream = MagicMock()
        mock_stream_class.return_value = mock_stream

        result = llm.chat(mock_chat_context)

        assert result == mock_stream
        mock_stream_class.assert_called_once()

        # Verify the stream was created with correct parameters
        call_args = mock_stream_class.call_args
        assert call_args[0][0] == llm  # First arg is the LLM instance
        assert call_args[0][1] == mock_chat_context  # Second is chat context

    @patch('n8n_agent.N8nLLMStream')
    def test_chat_increments_turn_counter(self, mock_stream_class, mock_webhook_url, mock_chat_context):
        """Test that each chat() call increments the turn counter"""
        llm = N8nWebhookLLM(mock_webhook_url, "token")
        mock_stream_class.return_value = MagicMock()

        assert llm.turn_counter == 0

        llm.chat(mock_chat_context)
        assert llm.turn_counter == 1

        llm.chat(mock_chat_context)
        assert llm.turn_counter == 2

    @patch('n8n_agent.N8nLLMStream')
    def test_chat_extracts_user_message(self, mock_stream_class, mock_webhook_url, mock_chat_context):
        """Test that chat() correctly extracts user messages"""
        llm = N8nWebhookLLM(mock_webhook_url, "token")

        llm.chat(mock_chat_context)

        # Get the payload that was passed to the stream
        call_args = mock_stream_class.call_args[0]
        payload = call_args[5]  # 6th argument is payload

        assert payload["input"]["text"] == "Hello, how are you?"
        assert payload["input"]["type"] == "text"
        assert payload["session_id"] == llm.session_id
        assert payload["turn_id"] == "t_1"

    @patch('n8n_agent.N8nLLMStream')
    def test_chat_handles_empty_context(self, mock_stream_class, mock_webhook_url, mock_chat_context_empty):
        """Test chat() handles empty chat context gracefully"""
        llm = N8nWebhookLLM(mock_webhook_url, "token")

        llm.chat(mock_chat_context_empty)

        call_args = mock_stream_class.call_args[0]
        payload = call_args[5]

        # Should have empty text when no messages
        assert payload["input"]["text"] == ""

    @patch('n8n_agent.N8nLLMStream')
    def test_chat_with_complex_context(self, mock_stream_class, mock_webhook_url, mock_chat_context_complex):
        """Test chat() extracts the latest user message from complex context"""
        llm = N8nWebhookLLM(mock_webhook_url, "token")

        llm.chat(mock_chat_context_complex)

        call_args = mock_stream_class.call_args[0]
        payload = call_args[5]

        # Should extract the most recent user message
        assert payload["input"]["text"] == "Tell me about AI"

    @patch('n8n_agent.N8nLLMStream')
    def test_chat_with_optional_parameters(self, mock_stream_class, mock_webhook_url, mock_chat_context):
        """Test chat() handles optional parameters correctly"""
        llm = N8nWebhookLLM(mock_webhook_url, "token")
        mock_stream_class.return_value = MagicMock()

        # These parameters should be accepted but may not be used
        stream = llm.chat(
            mock_chat_context,
            temperature=0.7,
            n=1,
            parallel_tool_calls=False,
            tools=[],
            tool_choice=None,
            conn_options=None
        )

        assert stream is not None

    @patch('n8n_agent.N8nLLMStream')
    @patch('n8n_agent.logger')
    def test_chat_logs_debug_info(self, mock_logger, mock_stream_class, mock_webhook_url, mock_chat_context):
        """Test that chat() logs appropriate debug information"""
        llm = N8nWebhookLLM(mock_webhook_url, "token")
        mock_stream_class.return_value = MagicMock()

        llm.chat(mock_chat_context)

        # Verify debug logging was called
        assert mock_logger.debug.called
        assert mock_logger.info.called

    def test_cursors_tracking(self, mock_webhook_url):
        """Test that cursors dictionary is properly maintained"""
        llm = N8nWebhookLLM(mock_webhook_url, "token")

        assert llm._cursors == {}

        # Cursors are typically set by the stream, but we can test the structure
        mock_ctx = MagicMock()
        mock_message = MagicMock()
        llm._cursors[mock_ctx] = mock_message

        assert mock_ctx in llm._cursors
        assert llm._cursors[mock_ctx] == mock_message