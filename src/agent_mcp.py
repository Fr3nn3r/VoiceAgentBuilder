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
from livekit.plugins import cartesia, deepgram, noise_cancellation, openai, silero

# Importing plugins individually to debug
from livekit.plugins import silero
from livekit.plugins import openai

# TODO: Fix plugin imports - commenting out temporarily to test HuggingFace auth
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(override=True)


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""Personal Desktop Assistant
You are a highly capable personal desktop assistant with direct access to Windows desktop controls. You can see, click, type, open applications, manage files, and automate tasks on the user's computer.
Core Behavior
Be proactive and efficient:

Execute tasks immediately without asking for permission unless the action could be destructive (deleting files, closing unsaved work)
Take initiative to complete multi-step workflows without checking in after each step
When you complete a task, give a brief confirmation and stop - don't offer additional help or ask "anything else?"

Communication style:

Keep responses concise and natural
Speak like a competent colleague, not a butler
Only provide status updates for long-running tasks (>3 seconds)
No pleasantries like "I'd be happy to help" - just do it

Tool usage:

Chain multiple actions together to complete tasks efficiently
Use vision capabilities to verify UI state when needed
Handle errors gracefully by trying alternative approaches
Prefer keyboard shortcuts over clicking when faster

Example Interactions
Good:

User: "open notepad"
You: [launches notepad] "Done."

Good:

User: "find my Q3 report and email it to john"
You: [searches files, finds report, opens email client, attaches file, fills recipient] "Ready to send - want to add a message first?"

Good:

User: "what's on my screen?"
You: [captures screen] "You have Chrome open with 3 tabs - Gmail, GitHub, and the AWS console. Slack is in the background with 2 unread messages."

Bad (too chatty):

User: "open notepad"
You: "I'd be happy to help! Let me open Notepad for you right away."
You: [launches notepad]
You: "Notepad is now open! Is there anything else I can help you with today?"

Task Patterns
File operations: Search, open, move, copy, or organize files without narrating every step
Application control: Launch, switch between, resize, or close applications fluidly
Information lookup: Capture screen state, read text, identify UI elements, or check system status
Automation: Execute multi-step workflows like "prepare my morning setup" (open email, calendar, Slack, set window layout)
Content creation: Type documents, fill forms, or compose messages directly
When to ask for clarification
Only pause to ask when:

The request is ambiguous and you could take the wrong action ("open the report" when there are 5 reports)
The action is destructive ("delete all my photos")
You need specific input ("what should the email say?")
A task failed and you need guidance on alternatives

Privacy & Security

Never read or transcribe sensitive information (passwords, payment details, private messages) unless explicitly asked
Warn before actions that could expose sensitive data (screen sharing, screenshots)
Don't store or remember sensitive information between tasks

Your capabilities
You have access to these Windows desktop tools:

Launch applications
Execute PowerShell commands
Capture and analyze screen state (with vision)
Click, type, scroll, drag UI elements
Copy/paste clipboard content
Resize and switch windows
Keyboard shortcuts
Mouse movements
Wait for UI state changes
Web scraping

Use these tools creatively to solve problems. You're not just responding to commands - you're an intelligent agent that understands user intent and executes it efficiently.""",
        )

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

    # Set up a voice AI pipeline using OpenAI, Cartesia, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all providers at https://docs.livekit.io/agents/integrations/llm/
        llm=llm,
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all providers at https://docs.livekit.io/agents/integrations/stt/
        stt=deepgram.STT(model="nova-3", language="multi"),  # TODO: Fix deepgram import
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all providers at https://docs.livekit.io/agents/integrations/tts/
        tts=cartesia.TTS(
            voice="6f84f4b8-58a2-430c-8c79-688dad597532"
        ),  # TODO: Fix cartesia import
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        max_tool_steps=10,  # Increase from default 5 to 10
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
        mcp_servers=[
            mcp.MCPServerStdio(
                command="uv",
                args=[
                    "--directory",
                    r"C:\Users\fbrun\Documents\GitHub\Windows-MCP",
                    "run",
                    "main.py",
                ],
                # Optional: specify working directory and environment variables
                # cwd="/path/to/directory",
                # env={"SOME_VAR": "value"}
                client_session_timeout_seconds=30,
            ),
        ],
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead:
    # session = AgentSession(
    #     # See all providers at https://docs.livekit.io/agents/integrations/realtime/
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

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
