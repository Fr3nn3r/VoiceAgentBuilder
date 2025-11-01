"""
Abstract interface for conversation persistence.
Follows Dependency Inversion Principle: high-level code depends on this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ConversationData:
    """
    Data model for a complete conversation.
    Maps to Airtable 'Conversations' table schema.
    """

    # Core conversation data
    voice_agent_name: str
    transcript: str
    conversation_date: str  # ISO format: "2025-10-30"
    patient_name: Optional[str] = None
    phone_number: Optional[str] = None
    audio_recording_url: Optional[str] = None
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    birth_date: Optional[str] = None
    reason: Optional[str] = None

    # Technical logging - LiveKit session identifiers
    livekit_room_name: Optional[str] = None
    livekit_job_id: Optional[str] = None

    # Technical logging - Conversation metrics
    total_turns: Optional[int] = None
    user_turns: Optional[int] = None
    agent_turns: Optional[int] = None

    # Technical logging - AI model usage (OpenAI Realtime API)
    llm_prompt_tokens: Optional[int] = None
    llm_completion_tokens: Optional[int] = None
    llm_input_audio_tokens: Optional[int] = None
    llm_output_audio_tokens: Optional[int] = None

    # Technical logging - Speech processing metrics
    stt_audio_duration_seconds: Optional[float] = None
    tts_audio_duration_seconds: Optional[float] = None
    tts_characters_count: Optional[int] = None

    # Technical logging - Configuration info
    openai_model: Optional[str] = None
    openai_voice: Optional[str] = None
    test_mode: Optional[bool] = None


class ConversationPersistence(ABC):
    """
    Abstract base class for conversation persistence.

    Implementations can store to:
    - N8N webhooks (current)
    - Supabase (future)
    - Direct Airtable API (future)
    - Local files (test mode)
    """

    @abstractmethod
    async def store_conversation(self, data: ConversationData, audio_data: Optional[bytes] = None) -> bool:
        """
        Store a complete conversation.

        Args:
            data: ConversationData with all collected information
            audio_data: Optional MP3 audio data to upload

        Returns:
            True if successful, False otherwise

        Note:
            Implementations should handle errors gracefully and log failures.
            This method should NOT raise exceptions that would crash the agent.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        Cleanup resources (e.g., close HTTP sessions).
        Called during agent shutdown.
        """
        pass
