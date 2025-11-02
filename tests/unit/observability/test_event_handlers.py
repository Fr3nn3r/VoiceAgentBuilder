"""
Unit tests for observability event handlers.

Tests session lifecycle tracking and event handling.
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.observability.config import ObservabilityConfig
from src.observability.context import clear_trace_context, get_trace_id
from src.observability.event_handlers import ObservabilityEventHandler
from src.observability.langsmith_tracer import ObservabilityTracer


@pytest.fixture
def mock_ctx():
    """Create mock JobContext"""
    ctx = MagicMock()
    ctx.room = MagicMock()
    ctx.room.name = "test_room_123"
    ctx.room.remote_participants = {}
    return ctx


@pytest.fixture
def mock_session():
    """Create mock AgentSession"""
    session = MagicMock()
    return session


@pytest.fixture
def disabled_tracer():
    """Create disabled tracer for testing"""
    config = ObservabilityConfig(
        enabled=False,
        environment="dev",
        langsmith_api_key="",
        langsmith_project="",
    )
    return ObservabilityTracer(config)


@pytest.fixture
@patch("src.observability.langsmith_tracer.Client")
def enabled_tracer(mock_client_class):
    """Create enabled tracer for testing"""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    config = ObservabilityConfig(
        enabled=True,
        environment="dev",
        langsmith_api_key="lsv2_test_key",
        langsmith_project="test-project",
    )
    return ObservabilityTracer(config)


class TestObservabilityEventHandler:
    """Test ObservabilityEventHandler session lifecycle"""

    def setup_method(self):
        """Clear context before each test"""
        clear_trace_context()

    def teardown_method(self):
        """Clear context after each test"""
        clear_trace_context()

    def test_handler_initialization(self, disabled_tracer, mock_ctx):
        """Handler should initialize with tracer and context"""
        handler = ObservabilityEventHandler(
            tracer=disabled_tracer,
            ctx=mock_ctx,
            agent_name="Camille",
        )

        assert handler.tracer == disabled_tracer
        assert handler.ctx == mock_ctx
        assert handler.agent_name == "Camille"
        assert handler.session is None
        assert handler.trace_id is None

    async def test_on_session_start_disabled(
        self, disabled_tracer, mock_ctx, mock_session
    ):
        """Session start with disabled tracer should do nothing"""
        handler = ObservabilityEventHandler(
            tracer=disabled_tracer,
            ctx=mock_ctx,
            agent_name="Camille",
        )

        await handler.on_session_start(mock_session)

        # Should not create trace
        assert get_trace_id() is None
        assert handler.trace_id is None

    @patch("src.observability.langsmith_tracer.RunTree")
    async def test_on_session_start_enabled(
        self, mock_run_tree_class, enabled_tracer, mock_ctx, mock_session
    ):
        """Session start with enabled tracer should create trace"""
        mock_run = MagicMock()
        mock_run.post = MagicMock()
        mock_run_tree_class.return_value = mock_run

        handler = ObservabilityEventHandler(
            tracer=enabled_tracer,
            ctx=mock_ctx,
            agent_name="Camille",
        )

        await handler.on_session_start(mock_session)

        # Give async tasks time to complete
        await asyncio.sleep(0.01)

        # Should create trace
        assert handler.trace_id is not None
        assert handler.room_id == "test_room_123"
        assert handler.session == mock_session

        # Should have created RunTree
        mock_run_tree_class.assert_called_once()

    @patch("src.observability.langsmith_tracer.RunTree")
    async def test_on_session_start_with_participant(
        self, mock_run_tree_class, enabled_tracer, mock_ctx, mock_session
    ):
        """Session start should capture participant ID"""
        mock_run = MagicMock()
        mock_run.post = MagicMock()
        mock_run_tree_class.return_value = mock_run

        # Add mock participant
        mock_participant = MagicMock()
        mock_participant.sid = "participant_456"
        mock_ctx.room.remote_participants = {"p1": mock_participant}

        handler = ObservabilityEventHandler(
            tracer=enabled_tracer,
            ctx=mock_ctx,
            agent_name="Camille",
        )

        await handler.on_session_start(mock_session)

        # Give async tasks time to complete
        await asyncio.sleep(0.01)

        # Should capture participant ID
        assert handler.participant_id == "participant_456"

    async def test_on_session_end_disabled(self, disabled_tracer, mock_ctx):
        """Session end with disabled tracer should do nothing"""
        handler = ObservabilityEventHandler(
            tracer=disabled_tracer,
            ctx=mock_ctx,
            agent_name="Camille",
        )

        # Should not raise error even without session start
        await handler.on_session_end()

    @patch("src.observability.langsmith_tracer.RunTree")
    async def test_on_session_end_enabled(
        self, mock_run_tree_class, enabled_tracer, mock_ctx, mock_session
    ):
        """Session end should close trace"""
        mock_run = MagicMock()
        mock_run.post = MagicMock()
        mock_run.end = MagicMock()
        mock_run_tree_class.return_value = mock_run

        handler = ObservabilityEventHandler(
            tracer=enabled_tracer,
            ctx=mock_ctx,
            agent_name="Camille",
        )

        # Start session first
        await handler.on_session_start(mock_session)
        await asyncio.sleep(0.01)

        trace_id_before = handler.trace_id

        # End session
        await handler.on_session_end()
        await asyncio.sleep(0.01)

        # Should have ended RunTree
        mock_run.end.assert_called_once()

        # Should clear session state
        assert handler.session is None
        assert handler.trace_id is None

    @patch("src.observability.langsmith_tracer.RunTree")
    async def test_session_lifecycle_complete(
        self, mock_run_tree_class, enabled_tracer, mock_ctx, mock_session
    ):
        """Test complete session lifecycle"""
        mock_run = MagicMock()
        mock_run.post = MagicMock()
        mock_run.end = MagicMock()
        mock_run_tree_class.return_value = mock_run

        handler = ObservabilityEventHandler(
            tracer=enabled_tracer,
            ctx=mock_ctx,
            agent_name="Camille",
        )

        # Start session
        await handler.on_session_start(mock_session)
        await asyncio.sleep(0.01)

        assert handler.trace_id is not None
        assert handler.session is not None

        # End session
        await handler.on_session_end()
        await asyncio.sleep(0.01)

        # Verify both start and end called
        assert mock_run_tree_class.call_count == 1
        mock_run.end.assert_called_once()

    async def test_on_session_start_error_handling(
        self, enabled_tracer, mock_ctx, mock_session
    ):
        """Session start errors should be caught and logged"""
        # Make tracer.start_session raise an error
        enabled_tracer.start_session = AsyncMock(side_effect=Exception("LangSmith error"))

        handler = ObservabilityEventHandler(
            tracer=enabled_tracer,
            ctx=mock_ctx,
            agent_name="Camille",
        )

        # Should not raise exception
        await handler.on_session_start(mock_session)

        # Handler should still be usable
        assert handler.session == mock_session

    async def test_on_session_end_error_handling(
        self, enabled_tracer, mock_ctx, mock_session
    ):
        """Session end errors should be caught and logged"""
        # Make tracer.end_session raise an error
        enabled_tracer.end_session = AsyncMock(side_effect=Exception("LangSmith error"))

        handler = ObservabilityEventHandler(
            tracer=enabled_tracer,
            ctx=mock_ctx,
            agent_name="Camille",
        )

        # Set up minimal state
        handler.trace_id = "test-trace-123"

        # Should not raise exception
        await handler.on_session_end()

    def test_get_participant_id_no_participants(self, disabled_tracer, mock_ctx):
        """Should return None when no participants"""
        mock_ctx.room.remote_participants = {}

        handler = ObservabilityEventHandler(
            tracer=disabled_tracer,
            ctx=mock_ctx,
            agent_name="Camille",
        )

        participant_id = handler._get_participant_id()
        assert participant_id is None

    def test_get_participant_id_with_participant(self, disabled_tracer, mock_ctx):
        """Should return first participant SID"""
        mock_participant = MagicMock()
        mock_participant.sid = "p_123"
        mock_ctx.room.remote_participants = {"p1": mock_participant}

        handler = ObservabilityEventHandler(
            tracer=disabled_tracer,
            ctx=mock_ctx,
            agent_name="Camille",
        )

        participant_id = handler._get_participant_id()
        assert participant_id == "p_123"

    def test_get_participant_id_error_handling(self, disabled_tracer, mock_ctx):
        """Should handle errors gracefully when getting participant ID"""
        # Make remote_participants raise error
        mock_ctx.room.remote_participants = MagicMock(
            side_effect=Exception("Access error")
        )

        handler = ObservabilityEventHandler(
            tracer=disabled_tracer,
            ctx=mock_ctx,
            agent_name="Camille",
        )

        # Should return None on error, not raise
        participant_id = handler._get_participant_id()
        assert participant_id is None
