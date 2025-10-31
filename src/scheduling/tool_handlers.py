"""
Tool handlers for scheduling operations.

Implements the business logic for each scheduling tool.
Handlers are callables that process tool arguments and return results.
"""

import logging
from typing import Any, Dict

from livekit.agents import RunContext

from persistence.conversation_recorder import ConversationRecorder

from .webhook_client import SchedulingToolHandler

logger = logging.getLogger("scheduling.tool_handlers")


class CheckAvailabilityHandler:
    """Handler for checking appointment availability"""

    def __init__(self, tool_handler: SchedulingToolHandler):
        self.tool_handler = tool_handler

    async def __call__(self, raw_arguments: dict, context: RunContext) -> Dict[str, Any]:
        """
        Check if appointment slot is available.

        Args:
            raw_arguments: Dict with start_datetime and end_datetime
            context: LiveKit run context

        Returns:
            Dict with 'available' boolean or 'error' string
        """
        logger.info(f"[Tool] check_availability called with {raw_arguments}")
        try:
            result = await self.tool_handler.check_availability(
                raw_arguments["start_datetime"], raw_arguments["end_datetime"]
            )
            available = result.get("available", False)
            return {"available": available}
        except Exception as e:
            logger.error(f"[Tool] check_availability error: {e}")
            return {"error": str(e)}


class BookAppointmentHandler:
    """Handler for booking appointments"""

    def __init__(self, tool_handler: SchedulingToolHandler):
        self.tool_handler = tool_handler

    async def __call__(self, raw_arguments: dict, context: RunContext) -> Dict[str, Any]:
        """
        Book a confirmed appointment.

        Args:
            raw_arguments: Dict with start_datetime, end_datetime, summary
            context: LiveKit run context

        Returns:
            Dict with booking result or error
        """
        logger.info(f"[Tool] book_appointment called with {raw_arguments}")
        try:
            result = await self.tool_handler.book_appointment(
                raw_arguments["start_datetime"],
                raw_arguments["end_datetime"],
                raw_arguments["summary"],
            )
            return result
        except Exception as e:
            logger.error(f"[Tool] book_appointment error: {e}")
            return {"error": str(e)}


class LogAppointmentHandler:
    """Handler for logging appointment details"""

    def __init__(
        self, tool_handler: SchedulingToolHandler, recorder: ConversationRecorder
    ):
        self.tool_handler = tool_handler
        self.recorder = recorder

    async def __call__(self, raw_arguments: dict, context: RunContext) -> Dict[str, Any]:
        """
        Log appointment details to backend and capture in recorder.

        Args:
            raw_arguments: Dict with event, date, times, patient info
            context: LiveKit run context

        Returns:
            Dict with logging result or error
        """
        logger.info(f"[Tool] log_appointment_details called with {raw_arguments}")
        try:
            # Capture patient info in conversation recorder
            self.recorder.set_patient_info(
                patient_name=raw_arguments.get("patient_name"),
                phone_number=raw_arguments.get("phone_number"),
                birth_date=raw_arguments.get("birth_date"),
                reason=raw_arguments.get("reason"),
            )

            # Capture appointment info
            self.recorder.set_appointment_info(
                appointment_date=raw_arguments.get("date"),
                appointment_time=raw_arguments.get("start_time"),
            )

            # Log to backend via webhook
            result = await self.tool_handler.log_appointment_details(
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
