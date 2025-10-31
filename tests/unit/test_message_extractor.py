"""
Unit tests for message extraction utilities.

Tests text extraction from various LiveKit event structures.
Focus on different attribute patterns and edge cases.
"""

from unittest.mock import MagicMock

from src.conversation.message_extractor import extract_user_text, extract_agent_text


def test_extract_user_text_from_text_attribute():
    """Test extracting user text from event.text"""
    mock_event = MagicMock()
    mock_event.text = "Je voudrais un rendez-vous"

    result = extract_user_text(mock_event)

    assert result == "Je voudrais un rendez-vous"


def test_extract_user_text_from_transcript_attribute():
    """Test extracting user text from event.transcript"""
    mock_event = MagicMock()
    mock_event.text = None
    mock_event.transcript = "Bonjour docteur"

    result = extract_user_text(mock_event)

    assert result == "Bonjour docteur"


def test_extract_user_text_from_alternatives():
    """Test extracting user text from event.alternatives[0].text"""
    mock_alternative = MagicMock()
    mock_alternative.text = "À demain"

    mock_event = MagicMock()
    mock_event.text = None
    del mock_event.transcript
    mock_event.alternatives = [mock_alternative]

    result = extract_user_text(mock_event)

    assert result == "À demain"


def test_extract_user_text_returns_none_when_missing():
    """Test extract_user_text returns None when no text found"""
    mock_event = MagicMock()
    mock_event.text = None
    del mock_event.transcript
    del mock_event.alternatives

    result = extract_user_text(mock_event)

    assert result is None


def test_extract_agent_text_from_direct_text():
    """Test extracting agent text from item.text"""
    mock_item = MagicMock()
    mock_item.role = "assistant"
    mock_item.text = "Bien sûr, je peux vous aider"

    result = extract_agent_text(mock_item)

    assert result == "Bien sûr, je peux vous aider"


def test_extract_agent_text_from_content_string():
    """Test extracting agent text from item.content (string)"""
    mock_item = MagicMock()
    mock_item.role = "assistant"
    mock_item.text = None
    mock_item.content = "Quelle date vous conviendrait?"

    result = extract_agent_text(mock_item)

    assert result == "Quelle date vous conviendrait?"


def test_extract_agent_text_from_content_list():
    """Test extracting agent text from item.content[0] (list of strings)"""
    mock_item = MagicMock()
    mock_item.role = "assistant"
    mock_item.text = None
    mock_item.content = ["Le rendez-vous est confirmé"]

    result = extract_agent_text(mock_item)

    assert result == "Le rendez-vous est confirmé"


def test_extract_agent_text_from_content_list_with_object():
    """Test extracting agent text from item.content[0].text (list of objects)"""
    mock_content_item = MagicMock()
    mock_content_item.text = "Merci beaucoup"

    mock_item = MagicMock()
    mock_item.role = "assistant"
    mock_item.text = None
    mock_item.content = [mock_content_item]

    result = extract_agent_text(mock_item)

    assert result == "Merci beaucoup"


def test_extract_agent_text_ignores_non_assistant():
    """Test extract_agent_text returns None for non-assistant roles"""
    mock_item = MagicMock()
    mock_item.role = "user"
    mock_item.text = "This should be ignored"

    result = extract_agent_text(mock_item)

    assert result is None


def test_extract_agent_text_returns_none_when_missing():
    """Test extract_agent_text returns None when no text found"""
    mock_item = MagicMock()
    mock_item.role = "assistant"
    mock_item.text = None
    mock_item.content = None

    result = extract_agent_text(mock_item)

    assert result is None
