"""
Console mode for medical appointment scheduling agent.
Test the agent via text input/output without LiveKit room.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import aiohttp
from dotenv import load_dotenv
from livekit.agents import llm, RunContext, function_tool

logger = logging.getLogger("medical_agent_console")
load_dotenv(override=True)

# OpenAI configuration for console mode
OPENAI_MODEL = "gpt-4o"  # Standard model for console
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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


async def console_mode():
    """Run the medical agent in console mode"""

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    )

    print("=" * 70)
    print("CAMILLE - MEDICAL APPOINTMENT SCHEDULER (Console Mode)")
    print("=" * 70)
    print("\nLoading configuration...")

    # Load configuration
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    webhook_token = os.getenv("N8N_WEBHOOK_TOKEN", "")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not webhook_url:
        print("ERROR: N8N_WEBHOOK_URL must be set in .env")
        return
    if not openai_api_key:
        print("ERROR: OPENAI_API_KEY must be set in .env")
        return

    print(f"✓ Webhook URL: {webhook_url}")
    print(f"✓ OpenAI Model: {OPENAI_MODEL}")

    # Load system prompt
    system_prompt = load_system_prompt()
    print("✓ Loaded system prompt from prompts/camille.md")

    # Initialize tool handler
    tool_handler = SchedulingToolHandler(webhook_url, webhook_token)

    # Create scheduling tools
    scheduling_tools = create_scheduling_tools(tool_handler)
    print(f"✓ Created {len(scheduling_tools)} scheduling tools")

    # Create OpenAI LLM (standard, not Realtime)
    from livekit.plugins import openai as lk_openai

    llm_instance = lk_openai.LLM(model=OPENAI_MODEL)

    # Create chat context
    chat_ctx = llm.ChatContext()
    chat_ctx.append(role="system", text=system_prompt)

    print("\n" + "=" * 70)
    print("AGENT READY - Console Mode")
    print("=" * 70)

    # Display greeting (simulating voice mode)
    print("\n[CAMILLE]")
    print("  Part 1 (Fast): Bonjour, cabinet du docteur Fillion, Camille à l'appareil.")
    print("  Part 2 (LLM): <will be generated>")
    print()

    # Generate natural follow-up greeting (simulating Option B1)
    greeting_stream = llm_instance.chat(
        chat_ctx=chat_ctx,
        tools=scheduling_tools,
    )

    greeting_response = ""
    async for chunk in greeting_stream:
        if chunk.choices[0].delta.content:
            greeting_response += chunk.choices[0].delta.content

    # Add greeting to context
    if greeting_response:
        chat_ctx.append(role="assistant", text=greeting_response)
        print(f"[CAMILLE] {greeting_response}\n")

    print("=" * 70)
    print("Type 'quit' or 'exit' to end the conversation")
    print("=" * 70)
    print()

    # Conversation loop
    try:
        while True:
            # Get user input
            user_input = input("YOU: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("\n[CAMILLE] Au revoir! Bonne journée.")
                break

            # Check for emergency
            if check_for_emergency(user_input):
                print("\n[CAMILLE] ⚠️ Je ne peux pas gérer les urgences. En cas d'urgence médicale, composez le 15 immédiatement.")
                print("\n[System] Emergency detected. Ending conversation.")
                break

            # Add user message to context
            chat_ctx.append(role="user", text=user_input)

            # Get LLM response with tools
            print("\n[CAMILLE] ", end="", flush=True)

            response_text = ""
            stream = llm_instance.chat(
                chat_ctx=chat_ctx,
                tools=scheduling_tools,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    print(content, end="", flush=True)
                    response_text += content

                # Handle tool calls
                if chunk.choices[0].delta.tool_calls:
                    for tool_call in chunk.choices[0].delta.tool_calls:
                        if tool_call.function:
                            print(f"\n[Tool Call: {tool_call.function.name}]", flush=True)

            print("\n")  # New line after response

            # Add assistant response to context
            if response_text:
                chat_ctx.append(role="assistant", text=response_text)

    except KeyboardInterrupt:
        print("\n\n[System] Interrupted by user")
    except Exception as e:
        logger.error(f"[Error] {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await tool_handler.close()
        print("\n" + "=" * 70)
        print("Session ended. Au revoir!")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(console_mode())
