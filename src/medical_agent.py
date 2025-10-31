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
from datetime import datetime, timezone
from typing import Any, Dict

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentFalseInterruptionEvent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
)
from livekit import rtc
from livekit.plugins import noise_cancellation, openai, silero
from livekit.plugins.openai.realtime.realtime_model import TurnDetection

from persistence import ConversationData, create_persistence
from persistence.conversation_recorder import ConversationRecorder
from persistence.egress_recording import create_egress_recorder_from_env
from prompts import load_system_prompt
from scheduling import SchedulingToolHandler, create_scheduling_tools

logger = logging.getLogger("medical_agent")
load_dotenv(override=True)

# Agent configuration
AGENT_NAME = "Camille"

# OpenAI Realtime configuration
OPENAI_MODEL = "gpt-4o-realtime-preview-2024-12-17"
OPENAI_VOICE = "alloy"  # French-compatible voice

# Emergency handling removed - prompt handles emergency detection and response


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
