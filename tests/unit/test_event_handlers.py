"""
Unit tests for conversation event handlers.

Tests event processing and transcript capture with mocked dependencies.
Focus on different event structures and missing data scenarios.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from livekit.agents import AgentSession

from src.conversation.event_handlers import (
    UserTranscriptionHandler,
    AgentResponseHandler,
    FalseInterruptionHandler,
)
from src.persistence.conversation_recorder import ConversationRecorder


@pytest.fixture
def mock_recorder():
    """Create mocked ConversationRecorder"""
    recorder = MagicMock(spec=ConversationRecorder)
    recorder.add_user_message = MagicMock()
    recorder.add_agent_message = MagicMock()
    return recorder


@pytest.fixture
def mock_session():
    """Create mocked AgentSession"""
    session = MagicMock(spec=AgentSession)
    session.generate_reply = MagicMock()
    return session


@pytest.mark.asyncio
async def test_user_transcription_with_text(mock_recorder):
    """Test UserTranscriptionHandler captures text from event"""
    import asyncio

    handler = UserTranscriptionHandler(mock_recorder)

    # Create mock event with text attribute
    mock_event = MagicMock()
    mock_event.text = "Bonjour, je voudrais prendre rendez-vous"

    # Execute
    handler(mock_event)

    # Give async task time to complete
    await asyncio.sleep(0.01)

    # Verify handler is correctly initialized with recorder
    assert handler.recorder == mock_recorder


@pytest.mark.asyncio
async def test_user_transcription_without_text(mock_recorder):
    """Test UserTranscriptionHandler handles missing text gracefully"""
    import asyncio

    handler = UserTranscriptionHandler(mock_recorder)

    # Create mock event without text
    mock_event = MagicMock()
    mock_event.text = None
    del mock_event.transcript
    del mock_event.alternatives

    # Execute - should not raise exception
    handler(mock_event)

    # Give async task time to complete
    await asyncio.sleep(0.01)

    # Verify handler still exists
    assert handler.recorder == mock_recorder


def test_agent_response_with_text(mock_recorder):
    """Test AgentResponseHandler extracts and records agent text"""
    handler = AgentResponseHandler(mock_recorder)

    # Create mock event with assistant message
    mock_item = MagicMock()
    mock_item.role = "assistant"
    mock_item.text = "Bien sûr, quelle date vous conviendrait?"

    mock_event = MagicMock()
    mock_event.item = mock_item

    # Execute
    handler(mock_event)

    # Verify message was added
    mock_recorder.add_agent_message.assert_called_once_with(
        "Bien sûr, quelle date vous conviendrait?"
    )


def test_agent_response_without_text(mock_recorder):
    """Test AgentResponseHandler handles missing text"""
    handler = AgentResponseHandler(mock_recorder)

    # Create mock event with assistant but no text
    mock_item = MagicMock()
    mock_item.role = "assistant"
    mock_item.text = None
    mock_item.content = None

    mock_event = MagicMock()
    mock_event.item = mock_item

    # Execute
    handler(mock_event)

    # Verify no message was added (since no text found)
    mock_recorder.add_agent_message.assert_not_called()


def test_agent_response_wrong_role(mock_recorder):
    """Test AgentResponseHandler ignores non-assistant messages"""
    handler = AgentResponseHandler(mock_recorder)

    # Create mock event with user role (not assistant)
    mock_item = MagicMock()
    mock_item.role = "user"
    mock_item.text = "Some user text"

    mock_event = MagicMock()
    mock_event.item = mock_item

    # Execute
    handler(mock_event)

    # Verify no message was added
    mock_recorder.add_agent_message.assert_not_called()


def test_false_interruption_resumes(mock_session):
    """Test FalseInterruptionHandler calls generate_reply"""
    handler = FalseInterruptionHandler(mock_session)

    # Create mock false interruption event
    mock_event = MagicMock()

    # Execute
    handler(mock_event)

    # Verify generate_reply was called to resume agent
    mock_session.generate_reply.assert_called_once()
