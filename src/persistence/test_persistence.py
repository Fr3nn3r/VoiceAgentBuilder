"""
Test mode persistence implementation.
Logs conversation data to local JSON files instead of calling webhooks.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .interface import ConversationData, ConversationPersistence

logger = logging.getLogger("test_persistence")


class TestConversationPersistence(ConversationPersistence):
    """
    Test mode implementation that saves conversations to local JSON files.
    Useful for development and testing without hitting real N8N webhooks.
    """

    def __init__(self, output_dir: str = "logs/conversations"):
        """
        Args:
            output_dir: Directory where conversation JSON files will be saved
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[TEST MODE] Initialized - saving to {self.output_dir.absolute()}")

    async def store_conversation(
        self, data: ConversationData, audio_data: Optional[bytes] = None
    ) -> bool:
        """
        Store conversation data to local JSON file.
        Optionally saves audio file alongside JSON.

        Filename format: conversation_<timestamp>.json
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_filename = f"conversation_{timestamp}.json"
            json_filepath = self.output_dir / json_filename

            # Convert dataclass to dict
            payload = {
                "action": "store_conversation",
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
            }

            # Save audio file if provided
            if audio_data:
                audio_filename = f"conversation_{timestamp}.mp3"
                audio_filepath = self.output_dir / audio_filename
                with open(audio_filepath, "wb") as f:
                    f.write(audio_data)

                audio_size_mb = len(audio_data) / (1024 * 1024)
                logger.info(
                    f"[TEST MODE] Saved audio to {audio_filepath} ({audio_size_mb:.2f}MB)"
                )

                # Add audio file reference to payload
                payload["audio_file_local"] = str(audio_filepath)

            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}

            # Write JSON to file
            with open(json_filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

            logger.info(f"[TEST MODE] Saved conversation to {json_filepath}")
            logger.info(f"[TEST MODE] Payload: {json.dumps(payload, indent=2)}")

            return True

        except Exception as e:
            logger.error(
                f"[TEST MODE] Error saving conversation: {type(e).__name__}: {e}"
            )
            return False

    async def close(self):
        """No resources to clean up for file-based storage"""
        logger.info("[TEST MODE] Closing (no-op for file storage)")
