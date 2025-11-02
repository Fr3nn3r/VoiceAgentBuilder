"""
LangSmith tracer wrapper for observability.

Follows SOLID principles:
- Single Responsibility: Only manages LangSmith trace lifecycle
- Open/Closed: Extensible via subclassing, closed for modification
- Liskov Substitution: Can be swapped with NoOpTracer when disabled
- Dependency Inversion: Tools depend on this interface, not LangSmith SDK directly

Never raises exceptions - all errors are logged and suppressed to prevent
agent crashes.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from langsmith import Client
from langsmith.run_trees import RunTree

from .config import ObservabilityConfig
from .context import get_trace_id, get_trace_metadata

logger = logging.getLogger("observability.tracer")


class ObservabilityTracer:
    """
    Wrapper around LangSmith RunTree for session and tool tracing.

    Provides async-safe, non-blocking telemetry with automatic error handling.
    All methods are safe to call - exceptions are logged but never raised.

    Usage:
        tracer = ObservabilityTracer.from_env()
        await tracer.start_session(room_id="room_123", participant_id="p_456")
        async with tracer.tool_span("tool.book_appointment", inputs):
            result = await book_appointment(...)
        await tracer.end_session()
    """

    def __init__(self, config: ObservabilityConfig):
        """
        Initialize tracer with configuration.

        Args:
            config: ObservabilityConfig instance
        """
        self.config = config
        self.client: Optional[Client] = None
        self.session_run: Optional[RunTree] = None

        # Initialize LangSmith client if enabled
        if config.enabled:
            try:
                self.client = Client(api_key=config.langsmith_api_key)
                logger.info(
                    f"[Observability] Initialized LangSmith client for project: {config.langsmith_project}"
                )
            except Exception as e:
                logger.error(
                    f"[Observability] Failed to initialize LangSmith client: {e}"
                )
                self.client = None

    @classmethod
    def from_env(cls) -> "ObservabilityTracer":
        """
        Create tracer from environment variables.

        Returns:
            ObservabilityTracer instance (may be disabled if config invalid)
        """
        try:
            config = ObservabilityConfig.from_env()
            return cls(config)
        except Exception as e:
            logger.warning(
                f"[Observability] Failed to load config, observability disabled: {e}"
            )
            # Return disabled tracer as fallback
            return cls(
                ObservabilityConfig(
                    enabled=False,
                    environment="dev",
                    langsmith_api_key="",
                    langsmith_project="",
                )
            )

    async def start_session(
        self,
        room_id: str,
        participant_id: str,
        agent_name: str = "Camille",
        **metadata: Any,
    ) -> None:
        """
        Start a new session trace.

        Creates root RunTree span in LangSmith. All subsequent spans will be children.

        Args:
            room_id: LiveKit room identifier
            participant_id: LiveKit participant identifier
            agent_name: Voice agent name (default: "Camille")
            **metadata: Additional metadata to attach to session

        Example:
            await tracer.start_session(
                room_id=ctx.room.name,
                participant_id=participant.sid,
                agent_name="Camille"
            )
        """
        if not self.config.enabled or not self.client:
            return

        try:
            # Get trace context metadata
            trace_metadata = get_trace_metadata()
            trace_id = get_trace_id()

            # Build session metadata per PRD Section 8
            session_metadata = {
                "trace_id": trace_id,
                "room_id": room_id,
                "participant_id": participant_id,
                "environment": self.config.environment,
                "agent_name": agent_name,
                "timestamp_start": datetime.now(timezone.utc).isoformat(),
                **trace_metadata,
                **metadata,
            }

            # Create root RunTree for session
            self.session_run = RunTree(
                name="voice_session",
                run_type="chain",
                inputs={"session_metadata": session_metadata},
                project_name=self.config.langsmith_project,
                client=self.client,
            )

            # Post session start asynchronously (non-blocking)
            asyncio.create_task(self._post_run(self.session_run))

            logger.info(
                f"[Observability] Session started: trace_id={trace_id}, room={room_id}"
            )

        except Exception as e:
            logger.error(f"[Observability] Failed to start session: {e}")

    async def end_session(self, **outputs: Any) -> None:
        """
        End current session trace.

        Closes root RunTree span and sends final data to LangSmith.

        Args:
            **outputs: Session outputs (e.g., summary metrics, final state)

        Example:
            await tracer.end_session(
                total_turns=10,
                duration_seconds=120.5,
                appointment_booked=True
            )
        """
        if not self.config.enabled or not self.session_run:
            return

        try:
            # Get final trace metadata
            trace_metadata = get_trace_metadata()

            # Add end timestamp
            session_outputs = {
                "timestamp_end": datetime.now(timezone.utc).isoformat(),
                **trace_metadata,
                **outputs,
            }

            # End session run
            self.session_run.end(outputs=session_outputs)

            # Post session end SYNCHRONOUSLY to ensure completion before cleanup
            # This is critical - we must wait for the final post to complete
            await self._post_run(self.session_run)

            logger.info(
                f"[Observability] Session ended: trace_id={trace_metadata.get('trace_id')}"
            )

            # Clean up
            self.session_run = None

        except Exception as e:
            logger.error(f"[Observability] Failed to end session: {e}")

    @asynccontextmanager
    async def tool_span(self, tool_name: str, inputs: Dict[str, Any]):
        """
        Context manager for tool call tracing.

        Creates child span under session for tool execution.
        Automatically measures duration and handles errors.

        Args:
            tool_name: Tool identifier (e.g., "tool.book_appointment")
            inputs: Tool input arguments (will be redacted by caller)

        Yields:
            RunTree instance for tool span (can add metadata)

        Example:
            async with tracer.tool_span("tool.check_availability", {"start": "10:00"}):
                result = await check_availability(...)
        """
        if not self.config.enabled or not self.session_run:
            # Return dummy context manager if disabled
            yield None
            return

        tool_run = None
        try:
            # Create child span for tool
            tool_run = self.session_run.create_child(
                name=tool_name,
                run_type="tool",
                inputs=inputs,
            )

            # Start timing
            start_time = datetime.now(timezone.utc)

            yield tool_run

            # End timing
            end_time = datetime.now(timezone.utc)
            duration_ms = (end_time - start_time).total_seconds() * 1000

            # Add duration metadata
            if tool_run:
                tool_run.end(
                    outputs={
                        "tool_start_ms": start_time.isoformat(),
                        "tool_end_ms": end_time.isoformat(),
                        "tool_duration_ms": duration_ms,
                    }
                )

                # Post tool span asynchronously (fire-and-forget for < 1ms overhead)
                asyncio.create_task(self._post_run(tool_run))

                logger.debug(
                    f"[Observability] Tool span completed: {tool_name} ({duration_ms:.2f}ms)"
                )

        except Exception as e:
            logger.error(f"[Observability] Failed to create tool span: {e}")
            # Yield None to satisfy context manager protocol
            yield None
            if tool_run:
                try:
                    tool_run.end(error=str(e))
                    asyncio.create_task(self._post_run(tool_run))
                except Exception as post_error:
                    logger.error(
                        f"[Observability] Failed to post error span: {post_error}"
                    )

    async def create_span(
        self, name: str, run_type: str = "chain", **metadata: Any
    ) -> Optional[RunTree]:
        """
        Create generic child span under session.

        Used for turn-level spans (user_turn, agent_turn) in Week 4.

        Args:
            name: Span name (e.g., "user_turn", "agent_turn")
            run_type: LangSmith run type (chain, llm, tool, retriever)
            **metadata: Span metadata

        Returns:
            RunTree instance or None if disabled

        Example:
            span = await tracer.create_span(
                "user_turn",
                audio_duration_ms=1500,
                transcript_length=45
            )
        """
        if not self.config.enabled or not self.session_run:
            return None

        try:
            # Create child span
            span = self.session_run.create_child(
                name=name, run_type=run_type, inputs=metadata
            )

            # End immediately (for event-based spans)
            span.end()

            # Post asynchronously (fire-and-forget)
            asyncio.create_task(self._post_run(span))

            logger.debug(f"[Observability] Span created: {name}")

            return span

        except Exception as e:
            logger.error(f"[Observability] Failed to create span: {e}")
            return None

    async def _post_run(self, run: RunTree) -> None:
        """
        Post run to LangSmith asynchronously.

        Internal helper - never raises exceptions.

        Args:
            run: RunTree instance to post
        """
        try:
            # LangSmith SDK post is sync, run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, run.post)

        except Exception as e:
            logger.error(f"[Observability] Failed to post run to LangSmith: {e}")

    async def close(self) -> None:
        """
        Cleanup resources.

        Called during agent shutdown.
        """
        if self.session_run:
            try:
                await self.end_session()
            except Exception as e:
                logger.error(f"[Observability] Error during cleanup: {e}")

        logger.info("[Observability] Tracer closed")


class NoOpTracer(ObservabilityTracer):
    """
    No-op tracer for when observability is disabled.

    Follows Liskov Substitution Principle - can be used anywhere
    ObservabilityTracer is expected, but does nothing.
    """

    def __init__(self):
        # Don't call parent __init__ to avoid LangSmith client creation
        self.config = ObservabilityConfig(
            enabled=False,
            environment="dev",
            langsmith_api_key="",
            langsmith_project="",
        )
        self.client = None
        self.session_run = None

    async def start_session(self, *args, **kwargs) -> None:
        pass

    async def end_session(self, **kwargs) -> None:
        pass

    @asynccontextmanager
    async def tool_span(self, tool_name: str, inputs: Dict[str, Any]):
        yield None

    async def create_span(self, name: str, run_type: str = "chain", **metadata: Any):
        return None

    async def close(self) -> None:
        pass
