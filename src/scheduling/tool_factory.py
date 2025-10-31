"""
Factory for creating LiveKit scheduling tools.

Assembles tool schemas and handlers into LiveKit FunctionTool objects.
"""

from typing import List, Optional

from livekit import rtc
from livekit.agents import AgentSession, function_tool

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from persistence.conversation_recorder import ConversationRecorder

from .tool_handlers import (
    create_book_appointment_handler,
    create_check_availability_handler,
    create_log_appointment_handler,
)
from .tool_schemas import (
    BOOK_APPOINTMENT_SCHEMA,
    CHECK_AVAILABILITY_SCHEMA,
    LOG_APPOINTMENT_SCHEMA,
)
from .webhook_client import SchedulingToolHandler


def create_scheduling_tools(
    tool_handler: SchedulingToolHandler,
    recorder: ConversationRecorder,
    session: Optional[AgentSession] = None,
    room: Optional[rtc.Room] = None,
) -> List:
    """
    Create LiveKit FunctionTool objects for scheduling.

    Args:
        tool_handler: Webhook client for scheduling operations
        recorder: Conversation recorder for capturing patient info
        session: Optional LiveKit agent session (unused currently)
        room: Optional LiveKit room (for future close_call tool)

    Returns:
        List of LiveKit FunctionTool objects ready to use

    Example:
        >>> handler = SchedulingToolHandler("https://n8n.example.com", "token")
        >>> recorder = ConversationRecorder("Camille")
        >>> tools = create_scheduling_tools(handler, recorder)
        >>> len(tools)
        3
    """
    # Create handler functions using factory pattern
    check_availability_fn = create_check_availability_handler(tool_handler)
    book_appointment_fn = create_book_appointment_handler(tool_handler)
    log_appointment_fn = create_log_appointment_handler(tool_handler, recorder)

    # Assemble FunctionTool objects with schemas
    return [
        function_tool(check_availability_fn, raw_schema=CHECK_AVAILABILITY_SCHEMA),
        function_tool(book_appointment_fn, raw_schema=BOOK_APPOINTMENT_SCHEMA),
        function_tool(log_appointment_fn, raw_schema=LOG_APPOINTMENT_SCHEMA),
        # function_tool(close_call_fn, raw_schema=CLOSE_CALL_SCHEMA),  # DISABLED
    ]
