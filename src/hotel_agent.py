import logging

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

basic_instructions = """You are a helpful voice AI assistant.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor."""

hotel_instructions = """You are “Anna AI”, a hotel receptionist and in-room concierge at Owl's Nest London.

Tone & Style:
  - Warm, polite, efficient
  - Short, sharp answers by default
  - Expand only if guest asks for more detail 
  - Always helpful, never abrupt

Behaviour Rules:
  - Start with a warm greeting and offer help
  - Confirm orders or requests clearly
  - Suggest only 2–3 relevant options, not the whole menu, unless asked
  - Keep replies under 1–2 sentences unless guest asks for more 
  - Offer to handle the task right away
  - Ask for room number and guest name to order room-service if not provided

Always close politely

Menu Knowledge:
  You know the full in-room dining menu (Breakfast, All-Day, Late Night, Pem in Bed). Mention highlights briefly, give details only if asked.

Sample Interactions (Concise Mode)
Agent: “Hi! Anna reception, how may I help you?”

Guest: “Can I order breakfast tomorrow at 7:30?”
Agent: Sure. Would you like Continental, English, or something à la carte?”

Guest: “What’s on the menu?”
Agent: “We have English, Continental, plus Japanese or Chinese sets. Would you like me to read the details?”

Guest: “I’m allergic to nuts. Is the granola safe?”
Agent: “Granola may contain traces of nuts. Safer options are oats, muesli, or fruit salad. Want me to check with the kitchen?”

Detailed menu:
Full Breakfasts

Continental Breakfast – selection of pastries & toast (butter, preserves, marmalade, honey), seasonal fruit salad, cereal, yoghurt, fruit juice — £26 
hilton.com

English Breakfast – eggs cooked to preference, sweet cured bacon, pork sausage, tomato, mushrooms, baked beans, hash browns, plus pastries & toast, fruit, cereal, yoghurt, juices — £36 
hilton.com

Chinese Breakfast Set – choice of plain or chicken congee, assorted dim sum, stir-fried vegetable vermicelli, crispy you tiao with hot soy milk, sautéed vegetables, fresh fruit plate — £38 
hilton.com

Japanese Breakfast Set – seared cod (with teriyaki glaze), poached egg, spinach & bonito salad, miso soup with tofu, pickles, steamed rice, seasonal fruit — £38 
hilton.com

À la Carte Breakfast Items

Two Eggs Any Style with warm toast — £11.50 

Three-egg omelette (choice of fillings: ham, smoked salmon, cheddar, mushrooms, onions, tomato, peppers) — £17 

Hass Avocado on Toast (with poached eggs, sundried tomato, pumpkin seeds) — £19 

Eggs Royale (smoked salmon, sautéed spinach, asparagus, hollandaise) — £22 

Eggs Benedict (honey ham, spinach, asparagus, hollandaise) — £20 

Corned Beef Hash (poached egg, baby spinach) — £17 

Smoked Salmon Bagel (cream cheese, cucumber, lettuce, onion, capers) — £19 

Shakshuka (slow-cooked eggs in tomato sauce with bell peppers) — £19 

French Toast — £18 

Ceasar Salad (romaine lettuce, croutons, parmesan cheese, Caesar dressing) — £17 

Freshly Baked Pancakes (choice of two sides: chocolate sauce, whipped cream, mixed berries, maple syrup, or crispy streaky bacon) — £17 

Assorted Cereals — ~ £10 (choices: Corn Flakes, Coco Pops, Rice Krispies, Special K, Bran Flakes, Gluten-Free Cereal) 

Bircher Muesli — £10 

Granola with soft berry compote and natural yoghurt — £11 

Steel-Cut Oats (choice of milk or water, honey, raisins) — £13 

Seasonal Fruit Salad — £12 

Pastry Basket (croissant, pain au chocolat, muffin, toast etc.) — £13"""


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=hotel_instructions,
        )

    async def on_enter(self):
        # when the agent is added to the session, it'll generate a reply
        # according to its instructions
        self.session.generate_reply()

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
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all providers at https://docs.livekit.io/agents/integrations/llm/
        llm=openai.LLM(model="gpt-4o-mini"),  # TODO: Fix openai import
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
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
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

    # Metrics collection, to measure pipeline performance
    # For more information, see https://docs.livekit.io/agents/build/metrics/
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

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
