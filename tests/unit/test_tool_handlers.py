"""
Unit tests for scheduling tool handlers.

Tests business logic of tool handlers with mocked webhook client.
Focus on success paths and webhook failure scenarios.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from livekit.agents import RunContext

from src.persistence.conversation_recorder import ConversationRecorder
from src.scheduling.tool_handlers import (
    create_check_availability_handler,
    create_book_appointment_handler,
)
from src.scheduling.webhook_client import SchedulingToolHandler


@pytest.fixture
def mock_tool_handler():
    """Create mocked SchedulingToolHandler"""
    handler = MagicMock(spec=SchedulingToolHandler)
    handler.check_availability = AsyncMock()
    handler.book_appointment = AsyncMock()
    handler.log_appointment_details = AsyncMock()
    return handler


@pytest.fixture
def mock_recorder():
    """Create mocked ConversationRecorder"""
    recorder = MagicMock(spec=ConversationRecorder)
    recorder.set_patient_info = MagicMock()
    recorder.set_appointment_info = MagicMock()
    return recorder


@pytest.fixture
def mock_context():
    """Create mocked RunContext"""
    return MagicMock(spec=RunContext)


@pytest.mark.asyncio
async def test_check_availability_success(mock_tool_handler, mock_context):
    """Test check availability handler returns available=True on success"""
    # Setup
    mock_tool_handler.check_availability.return_value = {"available": True}
    handler_fn = create_check_availability_handler(mock_tool_handler)

    raw_args = {
        "start_datetime": "2025-11-15T10:30:00",
        "end_datetime": "2025-11-15T11:00:00"
    }

    # Execute
    result = await handler_fn(raw_args, mock_context)

    # Verify
    assert result == {"available": True}
    mock_tool_handler.check_availability.assert_called_once_with(
        "2025-11-15T10:30:00", "2025-11-15T11:00:00"
    )


@pytest.mark.asyncio
async def test_check_availability_webhook_failure(mock_tool_handler, mock_context):
    """Test check availability handler handles webhook errors gracefully"""
    # Setup - webhook returns error
    mock_tool_handler.check_availability.return_value = {
        "error": "timeout",
        "detail": "Request timed out"
    }
    handler_fn = create_check_availability_handler(mock_tool_handler)

    raw_args = {
        "start_datetime": "2025-11-15T10:30:00",
        "end_datetime": "2025-11-15T11:00:00"
    }

    # Execute
    result = await handler_fn(raw_args, mock_context)

    # Verify - should return available=False when webhook fails
    assert result["available"] is False


@pytest.mark.asyncio
async def test_book_appointment_success(mock_tool_handler, mock_recorder, mock_context):
    """Test book appointment handler returns success on valid booking"""
    # Setup
    mock_tool_handler.book_appointment.return_value = {
        "status": "success",
        "event_id": "evt_123"
    }
    handler_fn = create_book_appointment_handler(mock_tool_handler, mock_recorder)

    raw_args = {
        "start_datetime": "2025-11-15T10:30:00",
        "end_datetime": "2025-11-15T11:00:00",
        "patient_name": "Jean Dupont",
        "birth_date": "1980-05-15",
        "phone_number": "0612345678",
        "reason": "Consultation générale",
        "comments": "Patient prefers morning appointments"
    }

    # Execute
    result = await handler_fn(raw_args, mock_context)

    # Verify recorder was updated
    mock_recorder.set_patient_info.assert_called_once_with(
        patient_name="Jean Dupont",
        phone_number="0612345678",
        birth_date="1980-05-15",
        reason="Consultation générale"
    )
    mock_recorder.set_appointment_info.assert_called_once_with(
        appointment_date="2025-11-15",
        appointment_time="10:30"
    )

    # Verify webhook was called with new parameters
    assert result["status"] == "success"
    assert result["event_id"] == "evt_123"
    mock_tool_handler.book_appointment.assert_called_once_with(
        "2025-11-15T10:30:00",
        "2025-11-15T11:00:00",
        "Jean Dupont",
        "1980-05-15",
        "0612345678",
        "Consultation générale",
        "Patient prefers morning appointments"
    )


@pytest.mark.asyncio
async def test_book_appointment_webhook_failure(mock_tool_handler, mock_recorder, mock_context):
    """Test book appointment handler returns error on webhook failure"""
    # Setup - simulate exception
    mock_tool_handler.book_appointment.side_effect = Exception("Network error")
    handler_fn = create_book_appointment_handler(mock_tool_handler, mock_recorder)

    raw_args = {
        "start_datetime": "2025-11-15T10:30:00",
        "end_datetime": "2025-11-15T11:00:00",
        "patient_name": "Jean Dupont",
        "phone_number": "0612345678",
        "reason": "Consultation"
    }

    # Execute
    result = await handler_fn(raw_args, mock_context)

    # Verify - recorder should still be updated even if webhook fails
    mock_recorder.set_patient_info.assert_called_once()
    mock_recorder.set_appointment_info.assert_called_once()

    # Verify - should return error dict instead of raising
    assert "error" in result
    assert "Network error" in result["error"]
