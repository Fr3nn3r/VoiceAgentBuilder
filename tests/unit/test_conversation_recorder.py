"""
Unit tests for ConversationRecorder.

Tests in-memory transcript recording and patient info tracking.
Focus on state management and data capture.
"""

import pytest
from datetime import datetime

from src.persistence.conversation_recorder import ConversationRecorder


@pytest.fixture
def recorder():
    """Create fresh ConversationRecorder"""
    return ConversationRecorder(voice_agent_name="Camille")


def test_add_user_message(recorder):
    """Test adding user message to transcript"""
    recorder.add_user_message("Bonjour, je voudrais un rendez-vous")

    assert recorder.get_turn_count() == 1
    assert len(recorder.turns) == 1
    assert recorder.turns[0].role == "user"
    assert recorder.turns[0].text == "Bonjour, je voudrais un rendez-vous"


def test_add_agent_message(recorder):
    """Test adding agent message to transcript"""
    recorder.add_agent_message("Bien sûr, quelle date vous conviendrait?")

    assert recorder.get_turn_count() == 1
    assert len(recorder.turns) == 1
    assert recorder.turns[0].role == "agent"
    assert recorder.turns[0].text == "Bien sûr, quelle date vous conviendrait?"


def test_alternating_messages(recorder):
    """Test recording alternating user and agent messages"""
    recorder.add_user_message("Je voudrais un rendez-vous")
    recorder.add_agent_message("Quelle date?")
    recorder.add_user_message("Demain à 10h")

    assert recorder.get_turn_count() == 3
    assert recorder.turns[0].role == "user"
    assert recorder.turns[1].role == "agent"
    assert recorder.turns[2].role == "user"


def test_set_patient_info(recorder):
    """Test setting patient information"""
    recorder.set_patient_info(
        patient_name="Jean Dupont",
        phone_number="0612345678",
        birth_date="1980-05-15",
        reason="Consultation générale"
    )

    assert recorder.patient_name == "Jean Dupont"
    assert recorder.phone_number == "0612345678"
    assert recorder.birth_date == "1980-05-15"
    assert recorder.reason == "Consultation générale"


def test_set_patient_info_partial(recorder):
    """Test setting patient info with only some fields"""
    recorder.set_patient_info(patient_name="Marie Dubois")
    assert recorder.patient_name == "Marie Dubois"
    assert recorder.phone_number is None

    # Update with more fields
    recorder.set_patient_info(phone_number="0698765432")
    assert recorder.patient_name == "Marie Dubois"  # Previous value preserved
    assert recorder.phone_number == "0698765432"


def test_set_appointment_info(recorder):
    """Test setting appointment information"""
    recorder.set_appointment_info(
        appointment_date="2025-11-15",
        appointment_time="10:30"
    )

    assert recorder.appointment_date == "2025-11-15"
    assert recorder.appointment_time == "10:30"


def test_get_full_transcript(recorder):
    """Test generating formatted transcript"""
    recorder.add_user_message("Bonjour")
    recorder.add_agent_message("Bonjour, comment puis-je vous aider?")
    recorder.add_user_message("Je voudrais un rendez-vous")

    transcript = recorder.get_full_transcript()

    assert "USER: Bonjour" in transcript
    assert "AGENT: Bonjour, comment puis-je vous aider?" in transcript
    assert "USER: Je voudrais un rendez-vous" in transcript


def test_get_summary(recorder):
    """Test generating conversation summary"""
    recorder.add_user_message("Bonjour")
    recorder.add_agent_message("Bonjour")
    recorder.add_user_message("Merci")

    recorder.set_patient_info(patient_name="Jean Dupont")
    recorder.set_appointment_info(appointment_date="2025-11-15")

    summary = recorder.get_summary()

    assert "Turns: 3" in summary
    assert "user: 2" in summary
    assert "agent: 1" in summary
    assert "Jean Dupont" in summary
    assert "2025-11-15" in summary


def test_empty_recorder(recorder):
    """Test recorder with no messages"""
    assert recorder.get_turn_count() == 0
    assert recorder.get_full_transcript() == ""
    assert recorder.patient_name is None
    assert recorder.appointment_date is None
