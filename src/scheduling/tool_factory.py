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
    create_calendar_agent_handler,
    create_check_availability_handler,
)
from .tool_schemas import (
    BOOK_APPOINTMENT_SCHEMA,
    CHECK_AVAILABILITY_SCHEMA,
    CALENDAR_AGENT_SCHEMA,
)
from .webhook_client import SchedulingToolHandler


def create_scheduling_tools(
    tool_handler: SchedulingToolHandler,
    recorder: ConversationRecorder,
    session: Optional[AgentSession] = None,
    room: Optional[rtc.Room] = None,
    observability_tracer=None,  # Week 3: Optional observability tracer
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
        2
    """
    # Create handler functions using factory pattern (Week 3: with observability)
    check_availability_fn = create_check_availability_handler(
        tool_handler, observability_tracer
    )
    book_appointment_fn = create_book_appointment_handler(
        tool_handler, recorder, observability_tracer
    )

    # Assemble FunctionTool objects with schemas
    return [
        function_tool(check_availability_fn, raw_schema=CHECK_AVAILABILITY_SCHEMA),
        function_tool(book_appointment_fn, raw_schema=BOOK_APPOINTMENT_SCHEMA),
        # function_tool(close_call_fn, raw_schema=CLOSE_CALL_SCHEMA),  # DISABLED
    ]


def create_calendar_agent_tool(
    tool_handler: SchedulingToolHandler, observability_tracer=None
):
    """
    Create LiveKit FunctionTool object for the secretary calendar agent.

    Args:
        tool_handler: Webhook client for scheduling operations
        observability_tracer: Optional tracer for observability (Week 3)

    Returns:
        Single FunctionTool configured for the calendar agent
    """
    calendar_agent_fn = create_calendar_agent_handler(
        tool_handler, observability_tracer
    )

    return function_tool(calendar_agent_fn, raw_schema=CALENDAR_AGENT_SCHEMA)
