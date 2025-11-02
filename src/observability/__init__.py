"""
Observability module for LangSmith tracing and monitoring.

Provides end-to-end session tracing for the medical voice agent with:
- Session lifecycle tracking
- Tool call instrumentation
- PHI/PII redaction
- TTFT-A (Time To First Token - Audio) measurement
- Async telemetry (< 1ms overhead)

Usage:
    from observability import ObservabilityTracer, ObservabilityEventHandler, FieldRedactor

    # Initialize tracer
    tracer = ObservabilityTracer.from_env()

    # Create event handler
    handler = ObservabilityEventHandler(tracer, room, job)

    # Redact PHI before sending
    redactor = FieldRedactor()
    safe_data = redactor.redact_phi(raw_data)
"""

from .config import ObservabilityConfig
from .context import get_trace_id, get_trace_metadata, set_trace_id, set_trace_metadata
from .event_handlers import ObservabilityEventHandler
from .langsmith_tracer import ObservabilityTracer
from .redaction import FieldRedactor, redact_phi

__all__ = [
    "ObservabilityConfig",
    "ObservabilityTracer",
    "ObservabilityEventHandler",
    "FieldRedactor",
    "redact_phi",
    "set_trace_id",
    "get_trace_id",
    "get_trace_metadata",
    "set_trace_metadata",
]
