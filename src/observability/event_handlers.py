"""
Observability event handlers for LiveKit session events.

Follows Single Responsibility Principle: Only listens to LiveKit events and creates spans.
Completely separate from conversation recording to maintain low coupling.

Week 2: Session start/end tracing
Week 4: Turn-level tracing (user_turn, agent_turn) + TTFT-A measurement
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from livekit import rtc
from livekit.agents import JobContext

from .context import add_session_end_timestamp, get_trace_id, set_trace_id, set_trace_metadata
from .langsmith_tracer import ObservabilityTracer

if TYPE_CHECKING:
    from livekit.agents import AgentSession

logger = logging.getLogger("observability.event_handlers")


class ObservabilityEventHandler:
    """
    Event handler for observability tracing.

    Listens to LiveKit session lifecycle events and creates traces in LangSmith.
    Completely isolated from conversation recording - follows SRP.

    Week 2 scope:
    - Session start/end events
    - Basic session metadata

    Week 4 scope (future):
    - Turn-level events (user_turn, agent_turn)
    - TTFT-A calculation from OpenAI Realtime events
    - Token usage tracking

    Usage:
        tracer = ObservabilityTracer.from_env()
        handler = ObservabilityEventHandler(
            tracer=tracer,
            ctx=ctx,
            agent_name="Camille"
        )
        await handler.on_session_start(session)
        # ... later ...
        await handler.on_session_end()
    """

    def __init__(
        self,
        tracer: ObservabilityTracer,
        ctx: JobContext,
        agent_name: str = "Camille",
    ):
        """
        Initialize observability event handler.

        Args:
            tracer: ObservabilityTracer instance for sending traces
            ctx: LiveKit JobContext for room/participant info
            agent_name: Voice agent name (default: "Camille")
        """
        self.tracer = tracer
        self.ctx = ctx
        self.agent_name = agent_name
        self.session: Optional["AgentSession"] = None

        # Session metadata
        self.room_id: Optional[str] = None
        self.participant_id: Optional[str] = None
        self.trace_id: Optional[str] = None

        logger.info(
            f"[Observability] Event handler initialized for agent: {agent_name}"
        )

    async def on_session_start(self, session: "AgentSession") -> None:
        """
        Handle session start event.

        Called when LiveKit agent session starts. Creates root trace in LangSmith
        with session metadata.

        Args:
            session: AgentSession instance from LiveKit

        Example:
            @session.on("agent_started")
            async def agent_started():
                await handler.on_session_start(session)
        """
        if not self.tracer.config.enabled:
            return

        try:
            self.session = session

            # Get room and participant info from context
            self.room_id = self.ctx.room.name
            self.participant_id = self._get_participant_id()

            # Initialize trace context
            self.trace_id = set_trace_id()
            set_trace_metadata("room_id", self.room_id)
            set_trace_metadata("participant_id", self.participant_id)
            set_trace_metadata("agent_name", self.agent_name)

            logger.info(
                f"[Observability] Session starting - trace_id={self.trace_id}, room={self.room_id}"
            )

            # Start LangSmith session trace
            await self.tracer.start_session(
                room_id=self.room_id,
                participant_id=self.participant_id or "unknown",
                agent_name=self.agent_name,
            )

            logger.info(
                f"[Observability] Session trace started successfully - trace_id={self.trace_id}"
            )

        except Exception as e:
            logger.error(f"[Observability] Failed to handle session start: {e}")

    async def on_session_end(self) -> None:
        """
        Handle session end event.

        Called when LiveKit agent session ends. Closes root trace in LangSmith
        with final metadata.

        Example:
            ctx.add_shutdown_callback(handler.on_session_end)
        """
        if not self.tracer.config.enabled or not self.trace_id:
            return

        try:
            # Add end timestamp to context
            add_session_end_timestamp()

            logger.info(
                f"[Observability] Session ending - trace_id={self.trace_id}"
            )

            # End LangSmith session trace with outputs
            await self.tracer.end_session(
                room_id=self.room_id,
                participant_id=self.participant_id,
                # Future: Add turn counts, duration, etc. from metrics collector (Week 4)
            )

            logger.info(
                f"[Observability] Session trace ended successfully - trace_id={self.trace_id}"
            )

            # Clean up
            self.session = None
            self.trace_id = None

        except Exception as e:
            logger.error(f"[Observability] Failed to handle session end: {e}")

    def _get_participant_id(self) -> Optional[str]:
        """
        Get remote participant ID from room.

        Returns:
            Participant SID or None if no remote participant found
        """
        try:
            # Get first remote participant (user)
            remote_participants = self.ctx.room.remote_participants
            if remote_participants:
                # Convert dict_values to list and get first participant
                first_participant = next(iter(remote_participants.values()), None)
                if first_participant:
                    return first_participant.sid
            return None
        except Exception as e:
            logger.warning(f"[Observability] Could not get participant ID: {e}")
            return None

    # Week 4: Turn-level event handlers (future implementation)
    # async def on_user_turn(self, event) -> None:
    #     """Handle user turn event - measures user speech duration"""
    #     pass
    #
    # async def on_agent_turn(self, event) -> None:
    #     """Handle agent turn event - measures TTFT-A and token usage"""
    #     pass
    #
    # async def on_tool_call(self, tool_name: str, inputs: dict, outputs: dict) -> None:
    #     """Handle tool call event - already implemented in tool_handlers (Week 3)"""
    #     pass
