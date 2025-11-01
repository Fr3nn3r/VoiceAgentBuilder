"""
Tool handlers for scheduling operations.

Implements the business logic for each scheduling tool.
Factory functions create async handler functions with proper closures.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict

from livekit.agents import RunContext

sys.path.append(str(Path(__file__).parent.parent))
from persistence.conversation_recorder import ConversationRecorder

from .webhook_client import SchedulingToolHandler

logger = logging.getLogger("scheduling.tool_handlers")


def create_check_availability_handler(
    tool_handler: SchedulingToolHandler,
) -> Callable:
    """
    Create handler function for checking appointment availability.

    Args:
        tool_handler: Webhook client for scheduling operations

    Returns:
        Async function that checks availability
    """

    async def check_availability_handler(
        raw_arguments: dict, context: RunContext
    ) -> Dict[str, Any]:
        """Check if appointment slot is available"""
        logger.info(f"[Tool] check_availability called with {raw_arguments}")
        try:
            result = await tool_handler.check_availability(
                raw_arguments["start_datetime"], raw_arguments["end_datetime"]
            )
            available = result.get("available", False)
            return {"available": available}
        except Exception as e:
            logger.error(f"[Tool] check_availability error: {e}")
            return {"error": str(e)}

    return check_availability_handler


def create_book_appointment_handler(
    tool_handler: SchedulingToolHandler, recorder: ConversationRecorder
) -> Callable:
    """
    Create handler function for booking appointments.

    Args:
        tool_handler: Webhook client for scheduling operations
        recorder: Conversation recorder for capturing patient info

    Returns:
        Async function that books appointments
    """

    async def book_appointment_handler(
        raw_arguments: dict, context: RunContext
    ) -> Dict[str, Any]:
        """Book a confirmed appointment and capture patient info"""
        logger.info(f"[Tool] book_appointment called with {raw_arguments}")
        try:
            # Extract patient info from arguments
            patient_name = raw_arguments.get("patient_name")
            phone_number = raw_arguments.get("phone_number")
            birth_date = raw_arguments.get("birth_date")
            reason = raw_arguments.get("reason")

            # Capture patient info in conversation recorder
            recorder.set_patient_info(
                patient_name=patient_name,
                phone_number=phone_number,
                birth_date=birth_date,
                reason=reason,
            )

            # Extract appointment date/time from start_datetime for recorder
            # Format: "2025-11-15T10:30:00" -> date="2025-11-15", time="10:30"
            start_datetime = raw_arguments["start_datetime"]
            if "T" in start_datetime:
                date_part, time_part = start_datetime.split("T")
                time_only = time_part.split(":")[0] + ":" + time_part.split(":")[1]  # HH:MM
                recorder.set_appointment_info(
                    appointment_date=date_part,
                    appointment_time=time_only,
                )

            # Call webhook to book appointment
            result = await tool_handler.book_appointment(
                raw_arguments["start_datetime"],
                raw_arguments["end_datetime"],
                patient_name,
                birth_date,
                phone_number,
                reason,
                raw_arguments.get("comments"),
            )
            return result
        except Exception as e:
            logger.error(f"[Tool] book_appointment error: {e}")
            return {"error": str(e)}

    return book_appointment_handler
