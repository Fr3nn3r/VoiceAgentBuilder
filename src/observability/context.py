"""
Trace context propagation using contextvars for async-safe state management.

Follows Single Responsibility Principle: only manages trace context lifecycle.
Uses Python's contextvars for proper async context isolation.
"""

import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Async-safe context variable for trace metadata
# Each async task gets its own isolated copy
trace_context: ContextVar[Dict[str, Any]] = ContextVar("trace_context", default={})


def set_trace_id(trace_id: Optional[str] = None) -> str:
    """
    Initialize trace context with a new trace ID.

    Args:
        trace_id: Optional trace ID (generates UUID if not provided)

    Returns:
        The trace ID that was set

    Example:
        trace_id = set_trace_id()
        # Later in async tasks...
        current_id = get_trace_id()  # Same ID, async-safe
    """
    if trace_id is None:
        trace_id = str(uuid.uuid4())

    ctx = trace_context.get().copy()
    ctx["trace_id"] = trace_id
    ctx["timestamp_start"] = datetime.now(timezone.utc).isoformat()
    trace_context.set(ctx)

    return trace_id


def get_trace_id() -> Optional[str]:
    """
    Get current trace ID from context.

    Returns:
        Trace ID if set, None otherwise

    Example:
        trace_id = get_trace_id()
        if trace_id:
            logger.info(f"Current trace: {trace_id}")
    """
    return trace_context.get().get("trace_id")


def set_trace_metadata(key: str, value: Any) -> None:
    """
    Add metadata to current trace context.

    Args:
        key: Metadata key
        value: Metadata value (must be JSON-serializable)

    Example:
        set_trace_metadata("room_id", room.name)
        set_trace_metadata("participant_id", participant.sid)
    """
    ctx = trace_context.get().copy()
    ctx[key] = value
    trace_context.set(ctx)


def get_trace_metadata() -> Dict[str, Any]:
    """
    Get all trace metadata from current context.

    Returns:
        Dictionary of all trace metadata

    Example:
        metadata = get_trace_metadata()
        logger.info(f"Trace metadata: {metadata}")
    """
    return trace_context.get().copy()


def clear_trace_context() -> None:
    """
    Clear trace context (useful for testing or cleanup).

    Example:
        clear_trace_context()  # Reset context
    """
    trace_context.set({})


def add_session_end_timestamp() -> None:
    """
    Add session end timestamp to trace context.

    Called when session ends to track total duration.
    """
    ctx = trace_context.get().copy()
    ctx["timestamp_end"] = datetime.now(timezone.utc).isoformat()
    trace_context.set(ctx)
