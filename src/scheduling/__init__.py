"""
Scheduling module for medical appointment booking.

Provides webhook-based scheduling tools for checking availability,
booking appointments, and logging appointment details.
"""

from .tool_factory import create_scheduling_tools
from .webhook_client import SchedulingToolHandler

__all__ = ["SchedulingToolHandler", "create_scheduling_tools"]
