"""
Conversation recorder that captures real-time transcript during agent sessions.
Tracks both user and agent messages with timestamps.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger("conversation_recorder")


@dataclass
class ConversationTurn:
    """Single turn in a conversation (user message or agent response)"""

    role: str  # "user" or "agent"
    text: str
    timestamp: str  # ISO format


@dataclass
class ConversationRecorder:
    """
    Records conversation transcript in real-time.
    Logs each turn to console for debugging.
    """

    voice_agent_name: str = "Camille"
    turns: List[ConversationTurn] = field(default_factory=list)
    patient_name: Optional[str] = None
    phone_number: Optional[str] = None
    birth_date: Optional[str] = None
    reason: Optional[str] = None
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None

    def add_user_message(self, text: str) -> None:
        """
        Add user message to transcript.
        Logs to console for real-time debugging.
        """
        turn = ConversationTurn(
            role="user", text=text, timestamp=datetime.now().isoformat()
        )
        self.turns.append(turn)
        logger.info(f"[Transcript] USER: {text}")

    def add_agent_message(self, text: str) -> None:
        """
        Add agent response to transcript.
        Logs to console for real-time debugging.
        """
        turn = ConversationTurn(
            role="agent", text=text, timestamp=datetime.now().isoformat()
        )
        self.turns.append(turn)
        logger.info(f"[Transcript] AGENT: {text}")

    def set_patient_info(
        self,
        patient_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        birth_date: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Update patient information as it's collected during the call"""
        if patient_name:
            self.patient_name = patient_name
        if phone_number:
            self.phone_number = phone_number
        if birth_date:
            self.birth_date = birth_date
        if reason:
            self.reason = reason

        logger.debug(
            f"[Transcript] Patient info updated: name={self.patient_name}, "
            f"phone={self.phone_number}, dob={self.birth_date}, reason={self.reason}"
        )

    def set_appointment_info(
        self, appointment_date: Optional[str] = None, appointment_time: Optional[str] = None
    ) -> None:
        """Update appointment information when booking is confirmed"""
        if appointment_date:
            self.appointment_date = appointment_date
        if appointment_time:
            self.appointment_time = appointment_time

        logger.debug(
            f"[Transcript] Appointment info updated: date={self.appointment_date}, "
            f"time={self.appointment_time}"
        )

    def get_full_transcript(self) -> str:
        """
        Get complete conversation transcript as formatted string.

        Format:
            [2025-10-30T14:23:45] USER: Bonjour...
            [2025-10-30T14:23:47] AGENT: Bonjour, cabinet du docteur Fillion...
        """
        lines = []
        for turn in self.turns:
            timestamp = turn.timestamp[:19]  # Trim microseconds
            role = turn.role.upper()
            lines.append(f"[{timestamp}] {role}: {turn.text}")

        return "\n".join(lines)

    def get_turn_count(self) -> int:
        """Get total number of conversation turns"""
        return len(self.turns)

    def get_summary(self) -> str:
        """Get brief summary of conversation state"""
        user_turns = sum(1 for t in self.turns if t.role == "user")
        agent_turns = sum(1 for t in self.turns if t.role == "agent")
        return (
            f"Turns: {len(self.turns)} (user: {user_turns}, agent: {agent_turns}), "
            f"Patient: {self.patient_name or 'unknown'}, "
            f"Appointment: {self.appointment_date or 'not set'}"
        )
