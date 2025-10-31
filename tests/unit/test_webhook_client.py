"""
Unit tests for SchedulingToolHandler webhook client.

Tests HTTP communication with N8N scheduling webhooks without external dependencies.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.scheduling.webhook_client import SchedulingToolHandler


@pytest.fixture
def handler():
    """Create SchedulingToolHandler instance for testing"""
    handler = SchedulingToolHandler(
        base_url="https://test.n8n.example.com", api_token="test_token_123"
    )
    # Create a mock session immediately to prevent real aiohttp usage
    mock_session = AsyncMock()
    mock_session.closed = False
    handler.session = mock_session
    return handler


@pytest.mark.asyncio
async def test_check_availability_success(handler):
    """Test successful availability check"""
    # Mock response context manager
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"available": True})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Configure session mock to return the response
    handler.session.post = MagicMock(return_value=mock_response)

    # Call method
    result = await handler.check_availability(
        "2025-11-15T10:30:00", "2025-11-15T11:00:00"
    )

    # Verify result
    assert result == {"available": True}


@pytest.mark.asyncio
async def test_book_appointment_success(handler):
    """Test successful appointment booking"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={"status": "success", "event_id": "evt_123"}
    )
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    handler.session.post = MagicMock(return_value=mock_response)

    result = await handler.book_appointment(
        "2025-11-15T10:30:00", "2025-11-15T11:00:00", "Medical Appointment | John Doe"
    )

    assert result["status"] == "success"
    assert "event_id" in result


@pytest.mark.asyncio
async def test_log_appointment_details(handler):
    """Test logging appointment details"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"logged": True})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    handler.session.post = MagicMock(return_value=mock_response)

    result = await handler.log_appointment_details(
        event="Booked",
        date="2025-11-15",
        start_time="10:30",
        end_time="11:00",
        patient_name="John Doe",
        birth_date="1990-05-15",
        phone_number="555-0123",
        reason="Annual checkup",
    )

    assert result["logged"] is True


@pytest.mark.asyncio
async def test_webhook_timeout(handler):
    """Test handling of webhook timeout"""
    handler.session.post = MagicMock(side_effect=asyncio.TimeoutError)

    result = await handler.check_availability(
        "2025-11-15T10:30:00", "2025-11-15T11:00:00"
    )

    assert result["error"] == "timeout"
    assert "timed out" in result["detail"]


@pytest.mark.asyncio
async def test_webhook_http_error(handler):
    """Test handling of HTTP error response"""
    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.text = AsyncMock(return_value="Internal Server Error")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    handler.session.post = MagicMock(return_value=mock_response)

    result = await handler.check_availability(
        "2025-11-15T10:30:00", "2025-11-15T11:00:00"
    )

    assert result["error"] == "HTTP 500"
    assert "Internal Server Error" in result["detail"]


@pytest.mark.asyncio
async def test_session_cleanup(handler):
    """Test proper session cleanup"""
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.close = AsyncMock()

    handler.session = mock_session

    await handler.close()

    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_authorization_header(handler):
    """Test that API token is included in Authorization header"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"available": True})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    handler.session.post = MagicMock(return_value=mock_response)

    await handler.check_availability("2025-11-15T10:30:00", "2025-11-15T11:00:00")

    # Verify Authorization header was included
    call_args = handler.session.post.call_args
    headers = call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test_token_123"
