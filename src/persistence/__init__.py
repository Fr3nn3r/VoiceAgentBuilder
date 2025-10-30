"""
Conversation persistence layer for voice agents.

Provides abstract interface and multiple implementations:
- N8nConversationPersistence: Production mode (N8N webhooks)
- TestConversationPersistence: Test mode (local JSON files)

Usage:
    from persistence import ConversationData, create_persistence

    # Create persistence layer based on environment
    persistence = create_persistence()

    # Store conversation data
    data = ConversationData(
        voice_agent_name="Camille",
        transcript="...",
        conversation_date="2025-10-30",
        ...
    )
    success = await persistence.store_conversation(data)
"""

import os
from typing import Optional

from .conversation_recorder import ConversationRecorder
from .interface import ConversationData, ConversationPersistence
from .n8n_persistence import N8nConversationPersistence
from .test_persistence import TestConversationPersistence

__all__ = [
    "ConversationData",
    "ConversationPersistence",
    "ConversationRecorder",
    "N8nConversationPersistence",
    "TestConversationPersistence",
    "create_persistence",
]


def create_persistence(
    webhook_url: Optional[str] = None,
    webhook_token: Optional[str] = None,
    test_mode: Optional[bool] = None,
) -> ConversationPersistence:
    """
    Factory function to create appropriate persistence implementation.

    Reads from environment variables:
    - TEST_MODE: "true" or "1" enables test mode
    - N8N_WEBHOOK_URL: Base URL for N8N webhooks
    - N8N_WEBHOOK_TOKEN: Optional Bearer token

    Args:
        webhook_url: Override N8N webhook URL (default: from env)
        webhook_token: Override N8N webhook token (default: from env)
        test_mode: Override test mode setting (default: from env)

    Returns:
        ConversationPersistence implementation (N8N or Test mode)
    """
    # Determine test mode
    if test_mode is None:
        test_mode_env = os.getenv("TEST_MODE", "false").lower()
        test_mode = test_mode_env in ("true", "1", "yes")

    if test_mode:
        return TestConversationPersistence()

    # Production mode: use N8N
    if webhook_url is None:
        webhook_url = os.getenv("N8N_WEBHOOK_URL")

    if webhook_token is None:
        webhook_token = os.getenv("N8N_WEBHOOK_TOKEN", "")

    if not webhook_url:
        raise ValueError(
            "N8N_WEBHOOK_URL must be set in environment when TEST_MODE is not enabled"
        )

    return N8nConversationPersistence(webhook_url, webhook_token)
