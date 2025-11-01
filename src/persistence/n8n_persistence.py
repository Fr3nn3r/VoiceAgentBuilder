"""
N8N webhook-based conversation persistence implementation.
Sends conversation data to N8N workflow that stores to Airtable.
"""

import logging
from typing import Optional

import aiohttp

from .interface import ConversationData, ConversationPersistence

logger = logging.getLogger("n8n_persistence")


class N8nConversationPersistence(ConversationPersistence):
    """
    Stores conversations by calling N8N webhook endpoint.
    N8N handles Airtable upsert logic for Patients, Appointments, and Conversations.
    """

    def __init__(self, base_url: str, api_token: Optional[str] = None, timeout: float = 10.0):
        """
        Args:
            base_url: Base URL for N8N webhook (e.g., https://n8n.example.com)
            api_token: Optional Bearer token for authentication
            timeout: Request timeout in seconds (default: 10s)
        """
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        logger.info(f"[N8N Persistence] Initialized with base URL: {self.base_url}")

    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def store_conversation(
        self, data: ConversationData, audio_data: Optional[bytes] = None
    ) -> bool:
        """
        Store conversation data via N8N webhook.

        Endpoint: POST {base_url}/store_conversation
        Payload matches Airtable schema expectations.

        Args:
            data: ConversationData with transcript and metadata
            audio_data: Optional MP3 audio data to upload

        Returns:
            True if successful, False otherwise
        """
        await self._ensure_session()

        url = f"{self.base_url}/store_conversation"

        # Build metadata payload
        metadata = {
            "action": "store_conversation",
            # Core conversation data
            "voice_agent_name": data.voice_agent_name,
            "audio_recording_url": data.audio_recording_url,
            "transcript": data.transcript,
            "conversation_date": data.conversation_date,
            "patient_name": data.patient_name,
            "phone_number": data.phone_number,
            "birth_date": data.birth_date,
            "appointment_date": data.appointment_date,
            "appointment_time": data.appointment_time,
            "reason": data.reason,
            # Technical logging - LiveKit session identifiers
            "livekit_room_name": data.livekit_room_name,
            "livekit_job_id": data.livekit_job_id,
            # Technical logging - Conversation metrics
            "total_turns": data.total_turns,
            "user_turns": data.user_turns,
            "agent_turns": data.agent_turns,
            # Technical logging - AI model usage
            "llm_prompt_tokens": data.llm_prompt_tokens,
            "llm_completion_tokens": data.llm_completion_tokens,
            "llm_input_audio_tokens": data.llm_input_audio_tokens,
            "llm_output_audio_tokens": data.llm_output_audio_tokens,
            # Technical logging - Speech processing metrics
            "stt_audio_duration_seconds": data.stt_audio_duration_seconds,
            "tts_audio_duration_seconds": data.tts_audio_duration_seconds,
            "tts_characters_count": data.tts_characters_count,
            # Technical logging - Configuration info
            "openai_model": data.openai_model,
            "openai_voice": data.openai_voice,
            "test_mode": data.test_mode,
        }

        # Remove None values to keep payload clean
        metadata = {k: v for k, v in metadata.items() if v is not None}

        logger.info(f"[N8N Persistence] Storing conversation to {url}")
        logger.debug(f"[N8N Persistence] Metadata: {metadata}")

        if audio_data:
            logger.info(
                f"[N8N Persistence] Including audio file ({len(audio_data) / 1024 / 1024:.2f}MB)"
            )

        try:
            # Prepare request based on whether we have audio
            if audio_data:
                # Send as multipart/form-data with audio file
                form_data = aiohttp.FormData()

                # Add metadata as JSON string with UTF-8 encoding
                import json

                form_data.add_field(
                    "metadata",
                    json.dumps(metadata, ensure_ascii=False),
                    content_type="application/json; charset=utf-8"
                )

                # Add audio file
                form_data.add_field(
                    "audio",
                    audio_data,
                    filename="recording.mp3",
                    content_type="audio/mpeg",
                )

                headers = {}
                if self.api_token:
                    headers["Authorization"] = f"Bearer {self.api_token}"

                async with self.session.post(
                    url,
                    data=form_data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout * 2),  # Double timeout for file upload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"[N8N Persistence] Success: {result}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"[N8N Persistence] HTTP {response.status}: {error_text}"
                        )
                        return False

            else:
                # Send metadata only as JSON with UTF-8 encoding
                import json

                headers = {"Content-Type": "application/json; charset=utf-8"}
                if self.api_token:
                    headers["Authorization"] = f"Bearer {self.api_token}"

                async with self.session.post(
                    url,
                    data=json.dumps(metadata, ensure_ascii=False).encode("utf-8"),
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"[N8N Persistence] Success: {result}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"[N8N Persistence] HTTP {response.status}: {error_text}"
                        )
                        return False

        except Exception as e:
            logger.error(
                f"[N8N Persistence] Error storing conversation: {type(e).__name__}: {e}"
            )
            return False

    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("[N8N Persistence] Session closed")
