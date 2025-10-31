"""
Tool handlers for scheduling operations.

Implements the business logic for each scheduling tool.
Factory functions create async handler functions with proper closures.
"""

import logging
from typing import Any, Callable, Dict

from livekit.agents import RunContext

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


def create_book_appointment_handler(tool_handler: SchedulingToolHandler) -> Callable:
    """
    Create handler function for booking appointments.

    Args:
        tool_handler: Webhook client for scheduling operations

    Returns:
        Async function that books appointments
    """

    async def book_appointment_handler(
        raw_arguments: dict, context: RunContext
    ) -> Dict[str, Any]:
        """Book a confirmed appointment"""
        logger.info(f"[Tool] book_appointment called with {raw_arguments}")
        try:
            result = await tool_handler.book_appointment(
                raw_arguments["start_datetime"],
                raw_arguments["end_datetime"],
                raw_arguments["summary"],
            )
            return result
        except Exception as e:
            logger.error(f"[Tool] book_appointment error: {e}")
            return {"error": str(e)}

    return book_appointment_handler


def create_log_appointment_handler(
    tool_handler: SchedulingToolHandler, recorder: ConversationRecorder
) -> Callable:
    """
    Create handler function for logging appointment details.

    Args:
        tool_handler: Webhook client for scheduling operations
        recorder: Conversation recorder for capturing patient info

    Returns:
        Async function that logs appointment details
    """

    async def log_appointment_handler(
        raw_arguments: dict, context: RunContext
    ) -> Dict[str, Any]:
        """Log appointment details to backend and capture in recorder"""
        logger.info(f"[Tool] log_appointment_details called with {raw_arguments}")
        try:
            # Capture patient info in conversation recorder
            recorder.set_patient_info(
                patient_name=raw_arguments.get("patient_name"),
                phone_number=raw_arguments.get("phone_number"),
                birth_date=raw_arguments.get("birth_date"),
                reason=raw_arguments.get("reason"),
            )

            # Capture appointment info
            recorder.set_appointment_info(
                appointment_date=raw_arguments.get("date"),
                appointment_time=raw_arguments.get("start_time"),
            )

            # Log to backend via webhook
            result = await tool_handler.log_appointment_details(
                event=raw_arguments["event"],
                date=raw_arguments["date"],
                start_time=raw_arguments["start_time"],
                end_time=raw_arguments["end_time"],
                patient_name=raw_arguments["patient_name"],
                birth_date=raw_arguments.get("birth_date"),
                phone_number=raw_arguments["phone_number"],
                reason=raw_arguments["reason"],
            )
            return result
        except Exception as e:
            logger.error(f"[Tool] log_appointment_details error: {e}")
            return {"error": str(e)}

    return log_appointment_handler
