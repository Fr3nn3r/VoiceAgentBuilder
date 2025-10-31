"""
Message extraction utilities for conversation events.

Handles the complex logic of extracting text from various event structures
in the LiveKit OpenAI Realtime API.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("conversation.message_extractor")


def extract_user_text(event: Any) -> Optional[str]:
    """
    Extract user text from transcription event.

    The event structure can vary, so we try multiple attributes.

    Args:
        event: User transcription event from LiveKit

    Returns:
        Extracted text string or None if not found
    """
    # Try common attributes where text might be
    if hasattr(event, "text") and event.text:
        return event.text

    if hasattr(event, "transcript") and event.transcript:
        return event.transcript

    if hasattr(event, "alternatives") and event.alternatives:
        # Try to get text from first alternative
        first_alt = event.alternatives[0]
        if hasattr(first_alt, "text"):
            return first_alt.text

    return None


def extract_agent_text(item: Any) -> Optional[str]:
    """
    Extract agent response text from conversation item.

    The OpenAI Realtime API can return text in various nested structures.
    This function tries all known patterns.

    Args:
        item: Conversation item from conversation_item_added event

    Returns:
        Extracted text string or None if not found

    Example structures handled:
        - item.text (direct string)
        - item.content (string)
        - item.content[0] (list of strings)
        - item.content[0].text (list of objects with text)
        - item.content.text (object with text)
    """
    # Only process assistant messages
    if not hasattr(item, "role") or item.role != "assistant":
        return None

    # Try direct text attribute
    if hasattr(item, "text") and item.text:
        logger.debug("[Extractor] Found text via item.text")
        return item.text

    # Try content attribute (multiple possible structures)
    if hasattr(item, "content") and item.content:
        content = item.content

        # Case 1: Content is a string directly
        if isinstance(content, str):
            logger.debug("[Extractor] Found text via item.content (str)")
            return content

        # Case 2: Content is a list
        if isinstance(content, list) and len(content) > 0:
            first_item = content[0]

            # Case 2a: List contains strings
            if isinstance(first_item, str):
                logger.debug("[Extractor] Found text via item.content[0] (str)")
                return first_item

            # Case 2b: List contains objects with .text
            if hasattr(first_item, "text"):
                logger.debug("[Extractor] Found text via item.content[0].text")
                return first_item.text

        # Case 3: Content is an object with .text
        if hasattr(content, "text"):
            logger.debug("[Extractor] Found text via item.content.text")
            return content.text

    return None
