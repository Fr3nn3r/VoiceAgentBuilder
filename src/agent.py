import logging
import os

from dotenv import load_dotenv
from livekit.agents import (
    NOT_GIVEN,
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
    metrics,
    mcp,
)
from livekit.agents.llm import function_tool
from livekit.plugins import (
    deepgram,
    elevenlabs,
    noise_cancellation,
    openai,
    silero,
)

# TODO: Fix plugin imports - commenting out temporarily to test HuggingFace auth
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(override=True)


# ElevenLabs multilingual voice handles all languages automatically
# River: Neutral, calm, supports en/it/fr/pt/zh
ELEVENLABS_VOICE_ID = "SAz9YHcvj6GT2YYXdXww"


class LanguageDetectionHandler:
    """Handles language detection from transcripts for logging purposes."""

    def __init__(self, session: AgentSession, threshold: int = 1):
        self.session = session
        self.threshold = threshold
        self.stable_detected = None
        self.stable_count = 0
        self.current_lang = "en"

    async def on_transcript(self, detected_lang: str | None):
        """Log detected language from transcript. ElevenLabs multilingual voice handles all languages automatically."""
        if not detected_lang:
            return

        # Track consecutive detections
        if detected_lang != self.stable_detected:
            self.stable_detected = detected_lang
            self.stable_count = 1
        else:
            self.stable_count += 1

        # Log language change if threshold met
        if (
            self.stable_count >= self.threshold
            and self.stable_detected != self.current_lang
        ):
            self.current_lang = detected_lang
            logger.info(f"Language detected: {detected_lang}")


class Assistant(Agent):
    def __init__(self, instructions_path: str = "prompts/shushu.md") -> None:
        # Load instructions from file
        with open(instructions_path, "r", encoding="utf-8") as f:
            instructions = f.read()

        super().__init__(instructions=instructions)

    # all functions annotated with @function_tool will be passed to the LLM when this
    # agent is active
    @function_tool
    async def lookup_weather(self, context: RunContext, location: str):
        """Use this tool to look up current weather information in the given location.

        If the location is not supported by the weather service, the tool will indicate this. You must tell the user the location's weather is unavailable.

        Args:
            location: The location to look up weather information for (e.g. city name)
        """

        logger.info(f"Looking up weather for {location}")

        return "sunny with a temperature of 70 degrees."

    @function_tool
    async def stop_conversation(self, context: RunContext):
        """Use this tool to stop the conversation and end the agent session.

        Call this when the user explicitly requests to end the conversation, hang up, or stop talking.
        """

        logger.info("User requested to stop conversation - closing session")

        # Close the agent session gracefully
        await context.session.aclose()

        return "Conversation ended successfully."


def prewarm(proc: JobProcess):
    # Load Silero VAD for voice activity detection
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Enhanced logging setup with structured logging
    ctx.log_context_fields = {
        "room": ctx.room.name,
        "session_id": getattr(ctx, "session_id", "unknown"),
    }

    llm = openai.LLM(model="gpt-4o")

    # Set up a voice AI pipeline using OpenAI, ElevenLabs, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all providers at https://docs.livekit.io/agents/integrations/llm/
        llm=llm,
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all providers at https://docs.livekit.io/agents/integrations/stt/
        stt=deepgram.STT(model="nova-3", language="multi"),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all providers at https://docs.livekit.io/agents/integrations/tts/
        tts=elevenlabs.TTS(
            voice_id=ELEVENLABS_VOICE_ID,
            model="eleven_multilingual_v2",
        ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        max_tool_steps=10,  # Increase from default 5 to 10
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead:
    # session = AgentSession(
    #     # See all providers at https://docs.livekit.io/agents/integrations/realtime/
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # Initialize language detection handler
    lang_handler = LanguageDetectionHandler(session, threshold=1)

    # Handle language detection from transcripts
    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev):
        import asyncio

        asyncio.create_task(lang_handler.on_transcript(ev.language))

    # sometimes background noise could interrupt the agent session, these are considered false positive interruptions
    # when it's detected, you may resume the agent's speech
    @session.on("agent_false_interruption")
    def _on_agent_false_interruption(ev: AgentFalseInterruptionEvent):
        logger.info("false positive interruption, resuming")
        session.generate_reply(instructions=ev.extra_instructions or NOT_GIVEN)

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/integrations/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/integrations/avatar/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
