"""
Medical appointment scheduling agent for Dr Fillion's office.
Uses LiveKit Agents + OpenAI Realtime API with webhook-based scheduling tools.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
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
from livekit.plugins import noise_cancellation, openai, silero
from livekit.plugins.openai.realtime.realtime_model import TurnDetection

logger = logging.getLogger("medical_agent")
load_dotenv(override=True)

# OpenAI Realtime configuration
OPENAI_MODEL = "gpt-4o-realtime-preview-2024-12-17"
OPENAI_VOICE = "alloy"  # French-compatible voice

# Emergency keywords that trigger immediate redirect
EMERGENCY_KEYWORDS_FR = [
    "urgence",
    "urgent",
    "douleur forte",
    "douleur intense",
    "difficulté à respirer",
    "respirer",
    "accident",
    "chute",
    "saigne",
    "saignement",
    "inconscient",
    "crise cardiaque",
    "coeur",
    "poitrine",
    "évanouissement",
    "convulsion",
    "brûlure grave",
]


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


def check_for_emergency(text: str) -> bool:
    """Check if text contains emergency keywords"""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in EMERGENCY_KEYWORDS_FR)


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
                    logger.error(
                        f"[Webhook] Error {response.status}: {error_text}"
                    )
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


def create_scheduling_tools(tool_handler: SchedulingToolHandler) -> list:
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
                raw_arguments["start_datetime"],
                raw_arguments["end_datetime"]
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

    # Create FunctionTool objects using raw schemas
    return [
        function_tool(check_availability_handler, raw_schema=check_availability_schema),
        function_tool(book_appointment_handler, raw_schema=book_appointment_schema),
        function_tool(log_appointment_handler, raw_schema=log_appointment_schema),
    ]


def prewarm(proc: JobProcess):
    """Preload models for faster startup"""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("[Prewarm] Loaded Silero VAD")


async def entrypoint(ctx: JobContext):
    """Main entry point for medical scheduling agent"""

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    )

    logger.info("[Medical Agent] Starting Camille - Dr Fillion appointment scheduler")

    # Load configuration
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    webhook_token = os.getenv("N8N_WEBHOOK_TOKEN", "")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not webhook_url:
        raise ValueError("N8N_WEBHOOK_URL must be set in environment")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY must be set in environment")

    logger.info(f"[Config] Webhook URL: {webhook_url}")
    logger.info(f"[Config] Model: {OPENAI_MODEL}")
    logger.info(f"[Config] Voice: {OPENAI_VOICE}")

    # Load system prompt
    system_prompt = load_system_prompt()
    logger.info("[Config] Loaded system prompt from prompts/camille.md")

    # Initialize tool handler
    tool_handler = SchedulingToolHandler(webhook_url, webhook_token)

    # Create scheduling tools
    scheduling_tools = create_scheduling_tools(tool_handler)
    logger.info(f"[Config] Created {len(scheduling_tools)} scheduling tools")

    # Create OpenAI Realtime session
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

    # Emergency detection: monitor user speech for emergency keywords
    @session.on("user_speech_committed")
    def on_user_speech(ev: Any):
        """Detect emergency keywords in user speech"""
        async def handle_emergency():
            if hasattr(ev, "text") and ev.text:
                text = ev.text
                logger.debug(f"[Speech] User said: {text}")

                if check_for_emergency(text):
                    logger.warning(f"[Emergency] Detected emergency keyword in: {text}")
                    # Interrupt and redirect to emergency services
                    emergency_message = "Je ne peux pas gérer les urgences. En cas d'urgence médicale, composez le 15 immédiatement."
                    await session.say(emergency_message, allow_interruptions=False)
                    # Log the emergency event
                    logger.critical(f"[Emergency] Call redirected to emergency services")
                    # Optionally disconnect after emergency redirect
                    await asyncio.sleep(2)
                    await ctx.room.disconnect()

        # Create task from synchronous callback
        asyncio.create_task(handle_emergency())

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

    ctx.add_shutdown_callback(log_usage)
    ctx.add_shutdown_callback(tool_handler.close)

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
    # LiveKit's cli.run_app handles both room mode and console mode automatically
    # Just run: python medical_agent.py console (for voice testing)
    # Or run: python medical_agent.py (for LiveKit room mode)
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
