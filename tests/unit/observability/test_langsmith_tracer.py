"""
Unit tests for LangSmith tracer wrapper.

Tests tracer lifecycle, error handling, and async behavior with mocked LangSmith SDK.
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.observability.config import ObservabilityConfig
from src.observability.context import clear_trace_context, get_trace_id, set_trace_id
from src.observability.langsmith_tracer import NoOpTracer, ObservabilityTracer


class TestObservabilityTracer:
    """Test ObservabilityTracer with mocked LangSmith SDK"""

    def setup_method(self):
        """Setup before each test"""
        clear_trace_context()

    def teardown_method(self):
        """Cleanup after each test"""
        clear_trace_context()

    def test_disabled_tracer_does_nothing(self):
        """Disabled tracer should not initialize LangSmith client"""
        config = ObservabilityConfig(
            enabled=False,
            environment="dev",
            langsmith_api_key="",
            langsmith_project="",
        )
        tracer = ObservabilityTracer(config)

        assert tracer.config.enabled is False
        assert tracer.client is None
        assert tracer.session_run is None

    @patch("src.observability.langsmith_tracer.Client")
    def test_enabled_tracer_initializes_client(self, mock_client_class):
        """Enabled tracer should initialize LangSmith client"""
        config = ObservabilityConfig(
            enabled=True,
            environment="dev",
            langsmith_api_key="lsv2_test_key",
            langsmith_project="test-project",
        )

        tracer = ObservabilityTracer(config)

        assert tracer.config.enabled is True
        mock_client_class.assert_called_once_with(api_key="lsv2_test_key")

    @patch("src.observability.langsmith_tracer.Client")
    def test_client_initialization_error_handled(self, mock_client_class):
        """Client init errors should be caught and logged"""
        mock_client_class.side_effect = Exception("API error")

        config = ObservabilityConfig(
            enabled=True,
            environment="dev",
            langsmith_api_key="lsv2_test_key",
            langsmith_project="test-project",
        )

        tracer = ObservabilityTracer(config)

        # Should handle error gracefully
        assert tracer.client is None

    @patch("src.observability.langsmith_tracer.Client")
    @patch("src.observability.langsmith_tracer.RunTree")
    async def test_start_session_creates_run_tree(self, mock_run_tree_class, mock_client_class):
        """start_session should create RunTree with session metadata"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_run = MagicMock()
        mock_run.post = MagicMock()
        mock_run_tree_class.return_value = mock_run

        config = ObservabilityConfig(
            enabled=True,
            environment="dev",
            langsmith_api_key="lsv2_test_key",
            langsmith_project="test-project",
        )

        tracer = ObservabilityTracer(config)
        set_trace_id("test-trace-123")

        await tracer.start_session(
            room_id="room_abc",
            participant_id="p_456",
            agent_name="Camille",
        )

        # Should create RunTree
        mock_run_tree_class.assert_called_once()
        call_kwargs = mock_run_tree_class.call_args[1]

        assert call_kwargs["name"] == "voice_session"
        assert call_kwargs["run_type"] == "chain"
        assert call_kwargs["project_name"] == "test-project"
        assert call_kwargs["client"] == mock_client

        # Verify metadata
        session_metadata = call_kwargs["inputs"]["session_metadata"]
        assert session_metadata["trace_id"] == "test-trace-123"
        assert session_metadata["room_id"] == "room_abc"
        assert session_metadata["participant_id"] == "p_456"
        assert session_metadata["agent_name"] == "Camille"
        assert session_metadata["environment"] == "dev"

        # Give async task time to complete
        await asyncio.sleep(0.01)

    async def test_start_session_disabled_does_nothing(self):
        """start_session on disabled tracer should do nothing"""
        config = ObservabilityConfig(
            enabled=False,
            environment="dev",
            langsmith_api_key="",
            langsmith_project="",
        )

        tracer = ObservabilityTracer(config)
        await tracer.start_session(room_id="room_abc", participant_id="p_456")

        # Should not create session_run
        assert tracer.session_run is None

    @patch("src.observability.langsmith_tracer.Client")
    @patch("src.observability.langsmith_tracer.RunTree")
    async def test_end_session_closes_run_tree(self, mock_run_tree_class, mock_client_class):
        """end_session should close RunTree with outputs"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_run = MagicMock()
        mock_run.post = MagicMock()
        mock_run.end = MagicMock()
        mock_run_tree_class.return_value = mock_run

        config = ObservabilityConfig(
            enabled=True,
            environment="dev",
            langsmith_api_key="lsv2_test_key",
            langsmith_project="test-project",
        )

        tracer = ObservabilityTracer(config)
        set_trace_id("test-trace-123")

        await tracer.start_session(room_id="room_abc", participant_id="p_456")
        await tracer.end_session(total_turns=10, duration_seconds=120.5)

        # Should end RunTree
        mock_run.end.assert_called_once()
        outputs = mock_run.end.call_args[1]["outputs"]
        assert "timestamp_end" in outputs
        assert outputs["total_turns"] == 10
        assert outputs["duration_seconds"] == 120.5

        # Session run should be cleared
        assert tracer.session_run is None

        # Give async task time to complete
        await asyncio.sleep(0.01)

    @patch("src.observability.langsmith_tracer.Client")
    @patch("src.observability.langsmith_tracer.RunTree")
    async def test_tool_span_creates_child_run(self, mock_run_tree_class, mock_client_class):
        """tool_span should create child RunTree for tool execution"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_session_run = MagicMock()
        mock_session_run.post = MagicMock()

        mock_tool_run = MagicMock()
        mock_tool_run.post = MagicMock()
        mock_tool_run.end = MagicMock()

        mock_session_run.create_child = MagicMock(return_value=mock_tool_run)
        mock_run_tree_class.return_value = mock_session_run

        config = ObservabilityConfig(
            enabled=True,
            environment="dev",
            langsmith_api_key="lsv2_test_key",
            langsmith_project="test-project",
        )

        tracer = ObservabilityTracer(config)
        await tracer.start_session(room_id="room_abc", participant_id="p_456")

        # Use tool span
        inputs = {"start_datetime": "2025-11-15T10:30:00"}
        async with tracer.tool_span("tool.book_appointment", inputs):
            await asyncio.sleep(0.001)  # Simulate tool execution

        # Should create child run
        mock_session_run.create_child.assert_called_once()
        call_kwargs = mock_session_run.create_child.call_args[1]
        assert call_kwargs["name"] == "tool.book_appointment"
        assert call_kwargs["run_type"] == "tool"
        assert call_kwargs["inputs"] == inputs

        # Should end with duration metadata
        mock_tool_run.end.assert_called_once()
        outputs = mock_tool_run.end.call_args[1]["outputs"]
        assert "tool_duration_ms" in outputs
        assert outputs["tool_duration_ms"] > 0

        # Give async task time to complete
        await asyncio.sleep(0.01)

    async def test_tool_span_disabled_yields_none(self):
        """tool_span on disabled tracer should yield None"""
        config = ObservabilityConfig(
            enabled=False,
            environment="dev",
            langsmith_api_key="",
            langsmith_project="",
        )

        tracer = ObservabilityTracer(config)

        async with tracer.tool_span("tool.test", {}) as span:
            assert span is None

    @patch("src.observability.langsmith_tracer.Client")
    @patch("src.observability.langsmith_tracer.RunTree")
    async def test_tool_span_error_handling(self, mock_run_tree_class, mock_client_class):
        """tool_span should handle errors gracefully"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_session_run = MagicMock()
        mock_session_run.post = MagicMock()
        mock_session_run.create_child = MagicMock(side_effect=Exception("LangSmith error"))

        mock_run_tree_class.return_value = mock_session_run

        config = ObservabilityConfig(
            enabled=True,
            environment="dev",
            langsmith_api_key="lsv2_test_key",
            langsmith_project="test-project",
        )

        tracer = ObservabilityTracer(config)
        await tracer.start_session(room_id="room_abc", participant_id="p_456")

        # Should handle error without raising
        async with tracer.tool_span("tool.test", {}):
            pass  # Should complete without exception

    def test_from_env_with_invalid_config(self):
        """from_env should return disabled tracer if config fails"""
        # Set invalid environment to trigger error
        with patch.dict(os.environ, {"OBSERVABILITY_ENABLED": "true"}, clear=True):
            # Missing required vars should trigger ValueError in config
            tracer = ObservabilityTracer.from_env()

            # Should return disabled tracer as fallback
            assert tracer.config.enabled is False


class TestNoOpTracer:
    """Test NoOpTracer stub implementation"""

    async def test_noop_tracer_does_nothing(self):
        """NoOpTracer should accept all calls but do nothing"""
        tracer = NoOpTracer()

        # All methods should work without errors
        await tracer.start_session(room_id="test", participant_id="test")
        await tracer.end_session()

        async with tracer.tool_span("tool.test", {}) as span:
            assert span is None

        result = await tracer.create_span("test_span")
        assert result is None

        await tracer.close()

        # No client should be created
        assert tracer.client is None
        assert tracer.session_run is None
