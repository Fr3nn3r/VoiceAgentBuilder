"""
Executive assistant agent for calendar coordination.

Uses LiveKit Agents + OpenAI Realtime API with a single calendar management tool.
Reuses webhook-based integrations for task execution.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
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

from conversation import (
    AgentResponseHandler,
    FalseInterruptionHandler,
    UserTranscriptionHandler,
)
from observability import ObservabilityEventHandler, ObservabilityTracer
from persistence import ConversationData, create_persistence
from persistence.conversation_recorder import ConversationRecorder
from persistence.egress_recording import create_egress_recorder_from_env
from prompts import load_system_prompt
from scheduling import SchedulingToolHandler, create_secretary_tools

logger = logging.getLogger("secretary_agent")
load_dotenv(override=True)

# Agent configuration
AGENT_NAME = "Sarah"

# OpenAI Realtime configuration
OPENAI_MODEL = "gpt-realtime-2025-08-28"
# OPENAI_MODEL = "gpt-realtime-mini-2025-10-06"
SUPPORTED_OPENAI_VOICES = {
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
}
OPENAI_VOICE = os.getenv("OPENAI_VOICE", "alloy").lower()

if OPENAI_VOICE not in SUPPORTED_OPENAI_VOICES:
    supported_list = ", ".join(sorted(SUPPORTED_OPENAI_VOICES))
    raise ValueError(
        f"Unsupported OPENAI_VOICE '{OPENAI_VOICE}'. Supported voices: {supported_list}"
    )


def prewarm(proc: JobProcess):
    """Preload models for faster startup"""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("[Prewarm] Loaded Silero VAD")


async def entrypoint(ctx: JobContext):
    """Main entry point for secretary scheduling agent"""

    # Configure logging
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    )

    if os.getenv("OPENAI_TRACE", "").lower() in {"true", "1", "yes", "debug"}:
        logging.getLogger("livekit.plugins.openai").setLevel(logging.DEBUG)
        logging.getLogger("livekit.plugins.openai.realtime").setLevel(logging.DEBUG)
        logging.getLogger("livekit.agents.voice").setLevel(logging.DEBUG)

    logger.info("[Secretary Agent] Starting Sarah - executive assistant")
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
    system_prompt = load_system_prompt("sarah-en")
    logger.info("[Config] Loaded system prompt from prompts/sarah-en.md")

    # Initialize conversation recorder
    recorder = ConversationRecorder(voice_agent_name=AGENT_NAME)
    logger.info(f"[Config] Initialized conversation recorder for {AGENT_NAME}")

    # Initialize observability tracer
    observability_tracer = ObservabilityTracer.from_env()
    if observability_tracer.config.enabled:
        logger.info(
            f"[Config] Observability enabled - environment: {observability_tracer.config.environment}"
        )
        logger.info(
            f"[Config] LangSmith project: {observability_tracer.config.langsmith_project}"
        )
    else:
        logger.info("[Config] Observability disabled")

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
                create_response=True,
            ),
        ),
        vad=ctx.proc.userdata["vad"],
    )

    # Create secretary tools with observability
    secretary_tools = create_secretary_tools(tool_handler, observability_tracer)
    logger.info(f"[Config] Created {len(secretary_tools)} secretary tools")

    # Initialize observability event handler
    observability_handler = ObservabilityEventHandler(
        tracer=observability_tracer,
        ctx=ctx,
        agent_name=AGENT_NAME,
    )

    # Register conversation event handlers
    user_handler = UserTranscriptionHandler(recorder)
    agent_handler = AgentResponseHandler(recorder)
    interruption_handler = FalseInterruptionHandler(session)

    @session.on("agent_state_changed")
    def on_agent_state_changed(ev):
        logger.debug(f"[State] Agent state {ev.old_state} -> {ev.new_state}")

    @session.on("user_state_changed")
    def on_user_state_changed(ev):
        logger.debug(f"[State] User state {ev.old_state} -> {ev.new_state}")

    @session.on("speech_created")
    def on_speech_created(ev):
        logger.info(
            f"[Speech] Created (source={ev.source}, user_initiated={ev.user_initiated})"
        )

    @session.on("error")
    def on_session_error(ev):
        err = getattr(ev.error, "message", repr(ev.error))
        logger.error(f"[Realtime] Error from {type(ev.source).__name__}: {err}")

    session.on("user_input_transcribed")(user_handler)
    session.on("conversation_item_added")(agent_handler)
    session.on("agent_false_interruption")(interruption_handler)

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
            azure_account = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
            azure_container = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
            if azure_account and azure_container:
                recording_url = f"https://{azure_account}.blob.core.windows.net/{azure_container}/recordings/{ctx.job.id}.mp4"
                logger.info(f"[Egress] Recording URL: {recording_url}")
            else:
                logger.warning(
                    "[Egress] Cannot build recording URL - missing Azure env vars"
                )

        audio_data = None

        usage_summary = usage_collector.get_summary()
        logger.info(f"[Metrics] Usage summary: {usage_summary}")

        user_turns_count = sum(1 for t in recorder.turns if t.role == "user")
        agent_turns_count = sum(1 for t in recorder.turns if t.role == "agent")

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
            audio_recording_url=recording_url,
            livekit_room_name=ctx.room.name,
            livekit_job_id=ctx.job.id,
            total_turns=recorder.get_turn_count(),
            user_turns=user_turns_count,
            agent_turns=agent_turns_count,
            llm_prompt_tokens=usage_summary.llm_prompt_tokens,
            llm_completion_tokens=usage_summary.llm_completion_tokens,
            llm_input_audio_tokens=usage_summary.llm_input_audio_tokens,
            llm_output_audio_tokens=usage_summary.llm_output_audio_tokens,
            stt_audio_duration_seconds=usage_summary.stt_audio_duration,
            tts_audio_duration_seconds=usage_summary.tts_audio_duration,
            tts_characters_count=usage_summary.tts_characters_count,
            openai_model=OPENAI_MODEL,
            openai_voice=OPENAI_VOICE,
            test_mode=test_mode,
        )

        logger.info("[Conversation] Calling N8N webhook...")
        try:
            success = await persistence.store_conversation(
                conversation_data, audio_data=audio_data
            )
            if success:
                logger.info("[Conversation] ✅ WEBHOOK SUCCESS - Data stored to N8N")
            else:
                logger.error(
                    "[Conversation] ❌ WEBHOOK FAILED - Check N8N logs for details"
                )
        except Exception as e:
            logger.error(
                f"[Conversation] ❌ WEBHOOK EXCEPTION: {type(e).__name__}: {e}"
            )

    async def close_egress():
        """Close egress recorder"""
        if egress_recorder:
            await egress_recorder.close()

    ctx.add_shutdown_callback(log_usage)
    ctx.add_shutdown_callback(store_conversation)
    ctx.add_shutdown_callback(tool_handler.close)
    ctx.add_shutdown_callback(close_egress)
    ctx.add_shutdown_callback(observability_handler.on_session_end)
    ctx.add_shutdown_callback(observability_tracer.close)

    agent = Agent(instructions=system_prompt, tools=secretary_tools)

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

    logger.info("[Secretary Agent] Agent connected and ready")

    await observability_handler.on_session_start(session)

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

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        """
        Handle participant disconnection to stop recording immediately.
        This prevents prolonged silence at the end of recordings.
        """
        logger.info(
            f"[Room] Participant disconnected: {participant.identity} (sid={participant.sid})"
        )

        async def handle_user_hangup():
            try:
                if egress_id and egress_recorder:
                    logger.info(
                        f"[Egress] Participant hung up - stopping recording {egress_id}"
                    )
                    stop_success = await egress_recorder.stop_recording(egress_id)
                    if stop_success:
                        logger.info("[Egress] Recording stopped successfully")
                    else:
                        logger.warning("[Egress] Failed to stop recording")

                logger.info("[Room] Waiting for cleanup tasks to complete...")
                await asyncio.sleep(3.0)

                logger.info(
                    "[Room] Initiating agent shutdown after participant disconnect"
                )
                ctx.shutdown(reason="Participant disconnected")

            except Exception as e:
                logger.error(f"[Room] Error handling participant disconnect: {e}")

        asyncio.create_task(handle_user_hangup())

    await asyncio.sleep(1.0)

    logger.info("[Greeting] Delivering automatic greeting...")

    # Determine time-of-day greeting in UTC+1 (Mr. Brunner's timezone)
    current_time_utc_plus_1 = datetime.now(timezone.utc) + timedelta(hours=1)
    hour = current_time_utc_plus_1.hour
    time_of_day = "morning" if hour < 12 else "afternoon"

    greeting_instruction = f"""Greet the caller with exactly this:
"Good {time_of_day}, Mr. Brunner. How can I help you?"
Keep the tone dynamic and energic."""

    try:
        speech_handle = await session.generate_reply(instructions=greeting_instruction)
        logger.info(
            "[Greeting] generate_reply returned handle=%s steps=%s",
            speech_handle,
            getattr(speech_handle, "num_steps", "n/a"),
        )
    except Exception as greeting_error:
        logger.exception("[Greeting] generate_reply raised: %s", greeting_error)
    else:
        logger.info("[Greeting] Greeting delivered via Realtime API")

    logger.info("[Secretary Agent] Agent ready and listening")


if __name__ == "__main__":

    if sys.platform == "win32":

        def exception_handler(loop, context):
            """Suppress common Windows asyncio shutdown exceptions"""
            exception = context.get("exception")
            if isinstance(exception, (ConnectionResetError, OSError, BrokenPipeError)):
                return
            loop.default_exception_handler(context)

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.set_exception_handler(exception_handler)
        except RuntimeError:
            logger.warning("Failed to set custom exception handler for asyncio.")

    try:
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
    except KeyboardInterrupt:
        logger.info("Secretary agent interrupted by user.")
