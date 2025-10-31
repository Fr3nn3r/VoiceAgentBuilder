"""
Medical appointment scheduling agent for Dr Fillion's office.
Uses LiveKit Agents + OpenAI Realtime API with webhook-based scheduling tools.
Includes conversation recording and persistence to Airtable via N8N.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import aiohttp
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentFalseInterruptionEvent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
    metrics,
)
from livekit import rtc
from livekit.plugins import noise_cancellation, openai, silero
from livekit.plugins.openai.realtime.realtime_model import TurnDetection

from persistence import ConversationData, create_persistence
from persistence.conversation_recorder import ConversationRecorder
from persistence.egress_recording import create_egress_recorder_from_env

logger = logging.getLogger("medical_agent")
load_dotenv(override=True)

# Agent configuration
AGENT_NAME = "Camille"

# OpenAI Realtime configuration
OPENAI_MODEL = "gpt-4o-realtime-preview-2024-12-17"
OPENAI_VOICE = "alloy"  # French-compatible voice

# Emergency handling removed - prompt handles emergency detection and response


def load_system_prompt() -> str:
    """Load Camille's system prompt from file"""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "prompts", "camille.md"
    )
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Replace the current time placeholder
            from datetime import timezone

            now_utc_plus_1 = datetime.now(timezone.utc) + timedelta(hours=1)
            content = content.replace(
                "{{ $now.setZone('UTC+1') }}", now_utc_plus_1.isoformat()
            )
            return content
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {prompt_path}")
        raise


# Emergency detection removed - prompt handles it


class SchedulingToolHandler:
    """Handles webhook calls for scheduling tools"""

    def __init__(self, base_url: str, api_token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def _call_webhook(
        self, endpoint: str, payload: Dict[str, Any], timeout: float = 8.0
    ) -> Dict[str, Any]:
        """Make HTTP POST request to webhook endpoint"""
        await self._ensure_session()

        url = f"{self.base_url}/{endpoint}"
        headers = {"Content-Type": "application/json"}

        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        logger.info(f"[Webhook] Calling {url} with payload: {payload}")

        try:
            async with self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"[Webhook] Success: {data}")
                    return data
                else:
                    error_text = await response.text()
                    logger.error(f"[Webhook] Error {response.status}: {error_text}")
                    return {"error": f"HTTP {response.status}", "detail": error_text}
        except asyncio.TimeoutError:
            logger.error(f"[Webhook] Timeout after {timeout}s")
            return {"error": "timeout", "detail": "Request timed out"}
        except Exception as e:
            logger.error(f"[Webhook] Exception: {type(e).__name__}: {e}")
            return {"error": str(type(e).__name__), "detail": str(e)}

    async def check_availability(
        self, start_datetime: str, end_datetime: str
    ) -> Dict[str, Any]:
        """Check if appointment slot is available"""
        payload = {
            "action": "check_availability",
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
        }
        result = await self._call_webhook("check_availability", payload)
        return result

    async def book_appointment(
        self, start_datetime: str, end_datetime: str, summary: str
    ) -> Dict[str, Any]:
        """Book an appointment"""
        payload = {
            "action": "book_appointment",
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "summary": summary,
        }
        result = await self._call_webhook("book_appointment", payload)
        return result

    async def log_appointment_details(
        self,
        event: str,
        date: str,
        start_time: str,
        end_time: str,
        patient_name: str,
        birth_date: Optional[str],
        phone_number: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Log appointment details to backend"""
        payload = {
            "action": "log_appointment",
            "event": event,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "patient_name": patient_name,
            "birth_date": birth_date,
            "phone_number": phone_number,
            "reason": reason,
        }
        result = await self._call_webhook("log_appointment", payload)
        return result

    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()


def create_scheduling_tools(
    tool_handler: SchedulingToolHandler,
    recorder: ConversationRecorder,
    session: Optional[AgentSession] = None,
    room: Optional[rtc.Room] = None,
) -> list:
    """Create FunctionTool objects for scheduling using raw schemas"""

    # Tool 1: Check availability
    check_availability_schema = {
        "type": "function",
        "name": "check_availability_true_false",
        "description": "Check if an appointment slot is available. Returns true if slot is free, false if occupied. MUST be called before booking.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_datetime": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format (e.g., '2025-11-15T10:30:00')",
                },
                "end_datetime": {
                    "type": "string",
                    "description": "End time in ISO 8601 format. Should be start + 30 minutes.",
                },
            },
            "required": ["start_datetime", "end_datetime"],
        },
    }

    async def check_availability_handler(raw_arguments: dict, context: RunContext):
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

    # Tool 2: Book appointment
    book_appointment_schema = {
        "type": "function",
        "name": "book_appointment",
        "description": "Book a confirmed appointment. Call ONLY ONCE after: (1) all patient info collected, (2) availability confirmed, (3) patient confirmed the time.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_datetime": {
                    "type": "string",
                    "description": "Confirmed appointment start time (ISO 8601)",
                },
                "end_datetime": {
                    "type": "string",
                    "description": "Confirmed appointment end time (ISO 8601)",
                },
                "summary": {
                    "type": "string",
                    "description": "Appointment summary in format: 'Medical Appointment | {patient_name}'",
                },
            },
            "required": ["start_datetime", "end_datetime", "summary"],
        },
    }

    async def book_appointment_handler(raw_arguments: dict, context: RunContext):
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

    # Tool 3: Log appointment details
    log_appointment_schema = {
        "type": "function",
        "name": "log_appointment_details",
        "description": "Log all appointment details. Call IMMEDIATELY after booking, ONLY ONCE per appointment.",
        "parameters": {
            "type": "object",
            "properties": {
                "event": {
                    "type": "string",
                    "description": "Event type: 'Booked', 'Cancelled', etc.",
                },
                "date": {"type": "string", "description": "Appointment date"},
                "start_time": {"type": "string", "description": "Start time"},
                "end_time": {"type": "string", "description": "End time"},
                "patient_name": {"type": "string", "description": "Full name"},
                "birth_date": {
                    "type": "string",
                    "description": "Birth date (for new patients)",
                },
                "phone_number": {"type": "string", "description": "Phone number"},
                "reason": {"type": "string", "description": "Reason for visit"},
            },
            "required": [
                "event",
                "date",
                "start_time",
                "end_time",
                "patient_name",
                "phone_number",
                "reason",
            ],
        },
    }

    async def log_appointment_handler(raw_arguments: dict, context: RunContext):
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

    # Tool 4: Close call (DISABLED - was closing before agent finished speaking)
    # close_call_schema = {
    #     "type": "function",
    #     "name": "close_call",
    #     "description": "End the call and hang up. Use this IMMEDIATELY after saying goodbye when the conversation is complete. This closes the session so the caller doesn't stay on the line.",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {},
    #         "required": [],
    #     },
    # }
    #
    # async def close_call_handler(raw_arguments: dict, context: RunContext):
    #     logger.info("[Tool] close_call called - disconnecting room")
    #     try:
    #         if room:
    #             # Disconnect the room which will trigger session close and shutdown callbacks
    #             await room.disconnect()
    #             logger.info("[Tool] Room disconnected successfully - call ended")
    #             return {"status": "success", "message": "Call ended"}
    #         else:
    #             logger.warning("[Tool] No room available to disconnect")
    #             return {"status": "warning", "message": "Room already disconnected"}
    #     except Exception as e:
    #         logger.error(f"[Tool] close_call error: {e}")
    #         return {"error": str(e)}

    # Create FunctionTool objects using raw schemas
    return [
        function_tool(check_availability_handler, raw_schema=check_availability_schema),
        function_tool(book_appointment_handler, raw_schema=book_appointment_schema),
        function_tool(log_appointment_handler, raw_schema=log_appointment_schema),
        # function_tool(close_call_handler, raw_schema=close_call_schema),  # DISABLED
    ]


def prewarm(proc: JobProcess):
    """Preload models for faster startup"""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("[Prewarm] Loaded Silero VAD")


async def entrypoint(ctx: JobContext):
    """Main entry point for medical scheduling agent"""

    # Configure logging
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    )

    logger.info("[Medical Agent] Starting Camille - Dr Fillion appointment scheduler")
    logger.info(f"[Config] Log Level: {log_level}")

    # Load configuration
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    webhook_token = os.getenv("N8N_WEBHOOK_TOKEN", "")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    test_mode = os.getenv("TEST_MODE", "false").lower() in ("true", "1", "yes")

    if not test_mode and not webhook_url:
        raise ValueError(
            "N8N_WEBHOOK_URL must be set in environment (or enable TEST_MODE)"
        )
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY must be set in environment")

    logger.info(f"[Config] Test Mode: {test_mode}")
    logger.info(
        f"[Config] Webhook URL: {webhook_url if not test_mode else 'N/A (test mode)'}"
    )
    logger.info(f"[Config] Model: {OPENAI_MODEL}")
    logger.info(f"[Config] Voice: {OPENAI_VOICE}")

    # Load system prompt
    system_prompt = load_system_prompt()
    logger.info("[Config] Loaded system prompt from prompts/camille.md")

    # Initialize conversation recorder
    recorder = ConversationRecorder(voice_agent_name=AGENT_NAME)
    logger.info(f"[Config] Initialized conversation recorder for {AGENT_NAME}")

    # Initialize Egress recorder for room audio recording
    egress_recorder = create_egress_recorder_from_env()
    if egress_recorder:
        logger.info("[Config] Egress recording enabled")
    else:
        logger.info("[Config] Egress recording disabled (missing S3/R2 credentials)")

    # Initialize persistence layer
    persistence = create_persistence(
        webhook_url=webhook_url, webhook_token=webhook_token, test_mode=test_mode
    )
    logger.info(f"[Config] Initialized persistence: {type(persistence).__name__}")

    # Initialize tool handler
    tool_handler = SchedulingToolHandler(
        webhook_url or "http://test.local", webhook_token
    )

    # Create OpenAI Realtime session (needed before creating tools with close_call)
    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            model=OPENAI_MODEL,
            voice=OPENAI_VOICE,
            temperature=0.8,
            modalities=["audio", "text"],
            turn_detection=TurnDetection(
                type="server_vad",
                threshold=0.5,
                prefix_padding_ms=300,
                silence_duration_ms=500,
                create_response=True,  # Must be explicitly set to avoid null error
            ),
        ),
        vad=ctx.proc.userdata["vad"],
    )

    # Create scheduling tools with recorder, session, and room
    scheduling_tools = create_scheduling_tools(
        tool_handler, recorder, session, ctx.room
    )
    logger.info(f"[Config] Created {len(scheduling_tools)} scheduling tools")

    # User speech monitoring: capture transcript + emergency detection
    @session.on("user_input_transcribed")
    def on_user_transcribed(ev: Any):
        """Capture user speech transcript and detect emergency keywords"""

        async def handle_speech():
            # Extract transcript text from event
            text = None
            if hasattr(ev, "text") and ev.text:
                text = ev.text
            elif hasattr(ev, "transcript") and ev.transcript:
                text = ev.transcript
            elif hasattr(ev, "alternatives") and ev.alternatives:
                # Try to get text from first alternative
                text = (
                    ev.alternatives[0].text
                    if hasattr(ev.alternatives[0], "text")
                    else None
                )

            if text:
                # Capture in transcript
                recorder.add_user_message(text)

        # Create task from synchronous callback
        asyncio.create_task(handle_speech())

    # Capture agent responses via conversation_item_added event
    @session.on("conversation_item_added")
    def on_conversation_item(ev: Any):
        """Capture agent responses when items are added to conversation"""
        logger.info("[Event] conversation_item_added event fired")
        logger.debug(f"[Event] Event object: {ev}")

        # Check if this is an agent message
        if hasattr(ev, "item"):
            item = ev.item
            item_role = getattr(item, "role", "unknown")
            logger.info(f"[Event] Item role: {item_role}")
            logger.debug(
                f"[Event] Item attributes: {[attr for attr in dir(item) if not attr.startswith('_')]}"
            )

            # Try to extract text from various possible structures
            text = None
            if hasattr(item, "role") and item.role == "assistant":
                if hasattr(item, "text") and item.text:
                    text = item.text
                    logger.debug(f"[Event] Found text via item.text")
                elif hasattr(item, "content") and item.content:
                    if isinstance(item.content, str):
                        text = item.content
                        logger.debug(f"[Event] Found text via item.content (str)")
                    elif isinstance(item.content, list) and len(item.content) > 0:
                        # Handle list of content items (can be strings or objects)
                        first_item = item.content[0]
                        if isinstance(first_item, str):
                            # List contains strings directly
                            text = first_item
                            logger.debug(
                                f"[Event] Found text via item.content[0] (str)"
                            )
                        elif hasattr(first_item, "text"):
                            # List contains objects with .text attribute
                            text = first_item.text
                            logger.debug(f"[Event] Found text via item.content[0].text")
                    elif hasattr(item.content, "text"):
                        text = item.content.text
                        logger.debug(f"[Event] Found text via item.content.text")

                if text:
                    logger.info(
                        f"[Event] Captured assistant message ({len(text)} chars)"
                    )
                    recorder.add_agent_message(text)
                else:
                    logger.warning(
                        f"[Event] Assistant item found but no text extracted"
                    )
                    logger.warning(
                        f"[Event] Item content type: {type(getattr(item, 'content', None))}"
                    )
                    logger.warning(
                        f"[Event] Item content value: {getattr(item, 'content', 'N/A')}"
                    )
        else:
            logger.warning(
                f"[Event] conversation_item_added fired but no 'item' attribute found"
            )
            logger.debug(
                f"[Event] Available attributes: {[attr for attr in dir(ev) if not attr.startswith('_')]}"
            )

    # Handle false positive interruptions
    @session.on("agent_false_interruption")
    def on_false_interruption(ev: AgentFalseInterruptionEvent):
        logger.info("[Agent] False positive interruption detected, resuming")
        session.generate_reply()

    # Metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"[Metrics] Session usage: {summary}")

    async def store_conversation():
        """Store conversation data on session end"""
        logger.info("[Conversation] Storing conversation data...")
        logger.info(f"[Conversation] Summary: {recorder.get_summary()}")

        # Get full transcript
        transcript = recorder.get_full_transcript()
        logger.debug(f"[Conversation] Full transcript:\n{transcript}")

        # Build recording URL from Egress (if recording was started)
        recording_url = None
        if egress_id:
            # Recording URL will be: https://<account>.blob.core.windows.net/<container>/recordings/<job_id>.mp4
            # This URL is publicly accessible after Egress completes
            azure_account = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
            azure_container = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
            if azure_account and azure_container:
                recording_url = (
                    f"https://{azure_account}.blob.core.windows.net/{azure_container}/recordings/{ctx.job.id}.mp4"
                )
                logger.info(f"[Egress] Recording URL: {recording_url}")
            else:
                logger.warning(
                    "[Egress] Cannot build recording URL - missing Azure env vars"
                )

        # No audio_data needed - Egress handles the recording
        audio_data = None

        # Build conversation data
        conversation_data = ConversationData(
            voice_agent_name=recorder.voice_agent_name,
            transcript=transcript,
            conversation_date=datetime.now(timezone.utc).date().isoformat(),
            patient_name=recorder.patient_name,
            phone_number=recorder.phone_number,
            birth_date=recorder.birth_date,
            reason=recorder.reason,
            appointment_date=recorder.appointment_date,
            appointment_time=recorder.appointment_time,
            audio_recording_url=recording_url,  # Egress recording URL
        )

        # Store via persistence layer (with audio)
        success = await persistence.store_conversation(
            conversation_data, audio_data=audio_data
        )
        if success:
            logger.info("[Conversation] Successfully stored conversation data")
        else:
            logger.error("[Conversation] Failed to store conversation data")

    async def close_egress():
        """Close egress recorder"""
        if egress_recorder:
            await egress_recorder.close()

    ctx.add_shutdown_callback(log_usage)
    ctx.add_shutdown_callback(store_conversation)
    ctx.add_shutdown_callback(persistence.close)
    ctx.add_shutdown_callback(tool_handler.close)
    ctx.add_shutdown_callback(close_egress)

    # Create agent with system prompt and tools
    agent = Agent(instructions=system_prompt, tools=scheduling_tools)

    # Start session
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Connect to room
    await ctx.connect()

    logger.info("[Medical Agent] Agent connected and ready")

    # Start Egress recording if enabled
    egress_id = None
    if egress_recorder:
        try:
            egress_id = await egress_recorder.start_room_recording(
                room_name=ctx.room.name,
                room_id=ctx.job.id,
            )
            if egress_id:
                logger.info(f"[Egress] Recording started with ID: {egress_id}")
            else:
                logger.warning("[Egress] Failed to start recording")
        except Exception as e:
            logger.error(f"[Egress] Error starting recording: {e}")

    # Detect when user hangs up and stop recording immediately
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        """
        Handle participant disconnection to stop recording immediately.
        This prevents 20+ seconds of silence at the end of recordings.
        """
        logger.info(
            f"[Room] Participant disconnected: {participant.identity} (sid={participant.sid})"
        )

        # Check if this is a remote participant (not the agent itself)
        # The agent's own disconnect will be handled by shutdown callbacks
        async def handle_user_hangup():
            try:
                # Stop egress recording immediately to prevent silence
                if egress_id and egress_recorder:
                    logger.info(
                        f"[Egress] User hung up - stopping recording {egress_id}"
                    )
                    stop_success = await egress_recorder.stop_recording(egress_id)
                    if stop_success:
                        logger.info("[Egress] Recording stopped successfully")
                    else:
                        logger.warning("[Egress] Failed to stop recording")

                # Shutdown agent gracefully (triggers shutdown callbacks for cleanup)
                logger.info("[Room] Initiating agent shutdown after user disconnect")
                ctx.shutdown(reason="User disconnected")

            except Exception as e:
                logger.error(f"[Room] Error handling user hangup: {e}")

        # Run async cleanup task
        asyncio.create_task(handle_user_hangup())

    # Deliver greeting immediately after connection
    # This works for both console mode and room mode
    await asyncio.sleep(1.0)  # Small delay to ensure everything is ready

    logger.info("[Greeting] Delivering automatic greeting...")

    # For OpenAI Realtime API, use generate_reply (it has built-in voice)
    # The greeting is in two parts per Option B1:
    # Part 1: Office identification + Part 2: How can I help
    greeting_instruction = """Greet the caller with exactly this:
    "Bonjour, cabinet du docteur Fillion, Camille à l'appareil."
    Then ask how you can help them in French, naturally and briefly."""

    await session.generate_reply(instructions=greeting_instruction)
    logger.info("[Greeting] Greeting delivered via Realtime API")

    logger.info("[Medical Agent] Agent ready and listening")


if __name__ == "__main__":

    # Suppress Windows-specific asyncio exceptions on shutdown
    if sys.platform == "win32":
        # Suppress ConnectionResetError and OSError on Windows during shutdown
        def exception_handler(loop, context):
            """Suppress common Windows asyncio shutdown exceptions"""
            exception = context.get("exception")
            if isinstance(exception, (ConnectionResetError, OSError, BrokenPipeError)):
                # These are expected during shutdown on Windows, don't log them
                return
            # Log other exceptions normally
            loop.default_exception_handler(context)

        # Set custom exception handler for asyncio
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.set_exception_handler(exception_handler)
        except RuntimeError:
            pass  # Loop not running yet

    try:
        # LiveKit's cli.run_app handles both room mode and console mode automatically
        # Just run: python medical_agent.py console (for voice testing)
        # Or run: python medical_agent.py (for LiveKit room mode)
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
    except KeyboardInterrupt:
        print("\n[INFO] Shutdown complete")
        sys.exit(0)
