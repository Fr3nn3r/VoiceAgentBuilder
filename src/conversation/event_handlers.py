"""
Event handlers for conversation transcript capture.

Implements handlers for LiveKit session events to capture user and agent messages.
Handlers are classes to enable testing and reusability.
"""

import asyncio
import logging
from typing import Any

from livekit.agents import AgentFalseInterruptionEvent, AgentSession

from persistence.conversation_recorder import ConversationRecorder

from .message_extractor import extract_agent_text, extract_user_text

logger = logging.getLogger("conversation.event_handlers")


class UserTranscriptionHandler:
    """
    Handler for user_input_transcribed events.

    Captures user speech and adds to conversation recorder.
    """

    def __init__(self, recorder: ConversationRecorder):
        """
        Initialize handler with recorder.

        Args:
            recorder: ConversationRecorder to store user messages
        """
        self.recorder = recorder

    def __call__(self, event: Any):
        """
        Handle user transcription event.

        This is a synchronous callback, so we create an async task.

        Args:
            event: user_input_transcribed event from LiveKit
        """

        async def handle_speech():
            text = extract_user_text(event)
            if text:
                self.recorder.add_user_message(text)

        # Create async task from synchronous callback
        asyncio.create_task(handle_speech())


class AgentResponseHandler:
    """
    Handler for conversation_item_added events.

    Captures agent responses when items are added to the conversation.
    """

    def __init__(self, recorder: ConversationRecorder):
        """
        Initialize handler with recorder.

        Args:
            recorder: ConversationRecorder to store agent messages
        """
        self.recorder = recorder

    def __call__(self, event: Any):
        """
        Handle conversation item added event.

        Extracts assistant messages and adds to recorder.

        Args:
            event: conversation_item_added event from LiveKit
        """
        logger.info("[Event] conversation_item_added event fired")
        logger.debug(f"[Event] Event object: {event}")

        # Check if event has an item
        if not hasattr(event, "item"):
            logger.warning(
                "[Event] conversation_item_added fired but no 'item' attribute found"
            )
            logger.debug(
                f"[Event] Available attributes: {[attr for attr in dir(event) if not attr.startswith('_')]}"
            )
            return

        item = event.item
        item_role = getattr(item, "role", "unknown")
        logger.info(f"[Event] Item role: {item_role}")
        logger.debug(
            f"[Event] Item attributes: {[attr for attr in dir(item) if not attr.startswith('_')]}"
        )

        # Extract text from item
        text = extract_agent_text(item)

        if text:
            logger.info(f"[Event] Captured assistant message ({len(text)} chars)")
            self.recorder.add_agent_message(text)
        else:
            # Only log warnings for assistant items (we don't care about user items here)
            if item_role == "assistant":
                logger.warning("[Event] Assistant item found but no text extracted")
                logger.warning(
                    f"[Event] Item content type: {type(getattr(item, 'content', None))}"
                )
                logger.warning(
                    f"[Event] Item content value: {getattr(item, 'content', 'N/A')}"
                )


class FalseInterruptionHandler:
    """
    Handler for agent_false_interruption events.

    Resumes agent reply when a false positive interruption is detected.
    """

    def __init__(self, session: AgentSession):
        """
        Initialize handler with session.

        Args:
            session: LiveKit AgentSession to resume
        """
        self.session = session

    def __call__(self, event: AgentFalseInterruptionEvent):
        """
        Handle false interruption event.

        Args:
            event: False interruption event from LiveKit
        """
        logger.info("[Agent] False positive interruption detected, resuming")
        self.session.generate_reply()
