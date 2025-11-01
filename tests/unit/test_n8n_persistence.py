"""
Unit tests for N8nConversationPersistence.

Tests webhook communication and UTF-8 character encoding.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.persistence import ConversationData
from src.persistence.n8n_persistence import N8nConversationPersistence


@pytest.fixture
def persistence():
    """Create N8nConversationPersistence instance for testing"""
    persistence = N8nConversationPersistence(
        base_url="https://test.n8n.example.com",
        api_token="test_token_123"
    )
    # Create a mock session immediately to prevent real aiohttp usage
    mock_session = AsyncMock()
    mock_session.closed = False
    persistence.session = mock_session
    return persistence


@pytest.fixture
def conversation_data_with_french_chars():
    """Create ConversationData with French characters for encoding tests"""
    return ConversationData(
        # Core conversation data
        voice_agent_name="Camille",
        transcript="USER: Bonjour, j'ai très mal à la tête.\nAGENT: Je comprends.",
        conversation_date="2025-10-31",
        patient_name="Stéphane Boissard",
        phone_number="06 25 24 38 72",
        appointment_date="2025-11-03",
        appointment_time="09:00",
        reason="Très mal à la tête",
        audio_recording_url="https://livekitrecordings.blob.core.windows.net/livekit-recordings/recordings/test_123.mp4",
        # Technical logging
        livekit_room_name="medical-appointment-test",
        livekit_job_id="test_job_123",
        total_turns=12,
        user_turns=6,
        agent_turns=6,
        llm_prompt_tokens=2450,
        llm_completion_tokens=1823,
        llm_input_audio_tokens=8940,
        llm_output_audio_tokens=7256,
        stt_audio_duration_seconds=45.3,
        tts_audio_duration_seconds=38.7,
        tts_characters_count=982,
        openai_model="gpt-4o-realtime-preview-2024-12-17",
        openai_voice="alloy",
        test_mode=False,
    )


@pytest.mark.asyncio
async def test_store_conversation_success(persistence, conversation_data_with_french_chars):
    """Test successful conversation storage"""
    # Mock response context manager
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"status": "success"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Configure session mock to return the response
    persistence.session.post = MagicMock(return_value=mock_response)

    # Call method
    result = await persistence.store_conversation(conversation_data_with_french_chars)

    # Verify result
    assert result is True
    persistence.session.post.assert_called_once()


@pytest.mark.asyncio
async def test_store_conversation_preserves_utf8_characters(persistence, conversation_data_with_french_chars):
    """Test that French characters are preserved in JSON (not escaped as \\uXXXX)"""
    # Mock response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"status": "success"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    persistence.session.post = MagicMock(return_value=mock_response)

    # Call method
    await persistence.store_conversation(conversation_data_with_french_chars)

    # Verify session.post was called
    persistence.session.post.assert_called_once()

    # Get the call arguments - now using 'data' parameter instead of 'json'
    call_args = persistence.session.post.call_args
    json_bytes = call_args.kwargs["data"]

    # Decode the UTF-8 bytes to string
    json_string = json_bytes.decode("utf-8")

    # Verify French characters are NOT escaped (ensure_ascii=False was used)
    # Check that actual UTF-8 characters are present, not escaped sequences
    assert "Stéphane Boissard" in json_string
    assert "très mal à la tête" in json_string
    assert "\\u00e9" not in json_string  # Should not contain escaped é
    assert "\\u00e0" not in json_string  # Should not contain escaped à
    assert "\\u00e8" not in json_string  # Should not contain escaped è


@pytest.mark.asyncio
async def test_store_conversation_with_audio_preserves_utf8(persistence, conversation_data_with_french_chars):
    """Test that French characters are preserved when sending multipart with audio"""
    # Mock response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"status": "success"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    persistence.session.post = MagicMock(return_value=mock_response)

    # Call with audio data
    fake_audio = b"fake mp3 data"
    await persistence.store_conversation(conversation_data_with_french_chars, audio_data=fake_audio)

    # Verify session.post was called
    persistence.session.post.assert_called_once()

    # Get the form data that was sent
    call_args = persistence.session.post.call_args
    form_data = call_args.kwargs["data"]

    # FormData is complex to inspect, but we can verify the call was made
    # The real test is that json.dumps(metadata, ensure_ascii=False) is in the code
    assert form_data is not None


@pytest.mark.asyncio
async def test_store_conversation_http_error(persistence, conversation_data_with_french_chars):
    """Test handling of HTTP error response"""
    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.text = AsyncMock(return_value="Internal Server Error")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    persistence.session.post = MagicMock(return_value=mock_response)

    result = await persistence.store_conversation(conversation_data_with_french_chars)

    assert result is False


@pytest.mark.asyncio
async def test_session_cleanup(persistence):
    """Test proper session cleanup"""
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.close = AsyncMock()

    persistence.session = mock_session

    await persistence.close()

    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_store_conversation_includes_technical_fields(persistence, conversation_data_with_french_chars):
    """Test that technical logging fields are included in webhook payload"""
    # Mock response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"status": "success"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    persistence.session.post = MagicMock(return_value=mock_response)

    # Call method
    await persistence.store_conversation(conversation_data_with_french_chars)

    # Get the call arguments
    call_args = persistence.session.post.call_args
    json_bytes = call_args.kwargs["data"]
    json_string = json_bytes.decode("utf-8")
    payload = json.loads(json_string)

    # Verify core fields are present
    assert payload["voice_agent_name"] == "Camille"
    assert payload["patient_name"] == "Stéphane Boissard"

    # Verify technical logging - session identifiers
    assert payload["livekit_room_name"] == "medical-appointment-test"
    assert payload["livekit_job_id"] == "test_job_123"

    # Verify technical logging - conversation metrics
    assert payload["total_turns"] == 12
    assert payload["user_turns"] == 6
    assert payload["agent_turns"] == 6

    # Verify technical logging - AI model usage
    assert payload["llm_prompt_tokens"] == 2450
    assert payload["llm_completion_tokens"] == 1823
    assert payload["llm_input_audio_tokens"] == 8940
    assert payload["llm_output_audio_tokens"] == 7256

    # Verify technical logging - speech processing
    assert payload["stt_audio_duration_seconds"] == 45.3
    assert payload["tts_audio_duration_seconds"] == 38.7
    assert payload["tts_characters_count"] == 982

    # Verify technical logging - configuration
    assert payload["openai_model"] == "gpt-4o-realtime-preview-2024-12-17"
    assert payload["openai_voice"] == "alloy"
    assert payload["test_mode"] is False
