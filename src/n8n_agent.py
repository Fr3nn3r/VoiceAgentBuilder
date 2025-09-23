import asyncio
import json
import logging
import os
import uuid
from typing import Optional, Dict, Any

import aiohttp
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
    WorkerOptions,
    cli,
    metrics,
)
from livekit.agents.llm import (
    LLM,
    LLMStream,
    ChatContext,
    ChatChunk,
    ChoiceDelta,
    ChatMessage,
)
from livekit.plugins import cartesia, deepgram, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("n8n_agent")

load_dotenv(override=True)


class N8nWebhookLLM(LLM):
    """Custom LLM that sends requests to n8n webhook instead of OpenAI"""

    def __init__(self, webhook_url: str, webhook_token: str, timeout: float = 8.0):
        super().__init__()
        self.webhook_url = webhook_url
        self.webhook_token = webhook_token
        self.timeout = timeout
        self.session_id = str(uuid.uuid4())
        self.turn_counter = 0
        self._cursors = {}  # Track conversation cursors

    def chat(
        self,
        chat_ctx: ChatContext,
        *,
        fnc_ctx: Optional[Any] = None,
        temperature: Optional[float] = None,
        n: Optional[int] = None,
        parallel_tool_calls: Optional[bool] = None,
        tools: Optional[list] = None,
        tool_choice: Optional[Any] = None,
        conn_options: Optional[Any] = None,
    ) -> "N8nLLMStream":
        """Create a stream for n8n webhook response"""
        logger.debug(f"[N8N] chat() called with turn #{self.turn_counter + 1}")
        self.turn_counter += 1

        # Debug what's in chat_ctx
        logger.debug(f"[N8N] ChatContext type: {type(chat_ctx)}")
        logger.debug(
            f"[N8N] ChatContext attributes: {[attr for attr in dir(chat_ctx) if not attr.startswith('_')]}"
        )

        # Extract the latest user message
        user_message = ""
        try:
            # Try different ways to access messages based on ChatContext structure
            messages = []

            # Try messages property
            if hasattr(chat_ctx, "messages"):
                messages = chat_ctx.messages
                logger.debug(f"[N8N] Found messages via .messages property")
            # Try items property
            elif hasattr(chat_ctx, "items"):
                messages = chat_ctx.items
                logger.debug(f"[N8N] Found messages via .items property")
            # Try as iterable
            elif hasattr(chat_ctx, "__iter__"):
                messages = list(chat_ctx)
                logger.debug(f"[N8N] Found messages via iteration")

            logger.debug(f"[N8N] Found {len(messages)} messages in context")

            # Extract the latest user message
            for msg in reversed(messages):
                logger.debug(
                    f"[N8N] Message: role={getattr(msg, 'role', 'unknown')}, content type={type(getattr(msg, 'content', None))}"
                )

                # Check if it's a user message
                if hasattr(msg, "role") and msg.role == "user":
                    content = getattr(msg, "content", None)

                    if isinstance(content, str):
                        user_message = content
                    elif isinstance(content, list):
                        # Handle list of content items
                        for item in content:
                            if isinstance(item, str):
                                user_message = item
                                break
                            elif hasattr(item, "text"):
                                user_message = item.text
                                break
                    elif hasattr(content, "text"):
                        user_message = content.text

                    if user_message:
                        logger.info(
                            f"[N8N] Successfully extracted user message: {user_message}"
                        )
                        break

        except Exception as e:
            logger.error(f"[N8N] Error extracting messages: {e}")
            import traceback

            logger.debug(f"[N8N] Traceback: {traceback.format_exc()}")
            user_message = ""  # Don't fallback to "Hello"

        # Prepare webhook payload
        payload = {
            "session_id": self.session_id,
            "turn_id": f"t_{self.turn_counter}",
            "input": {"type": "text", "text": user_message},
            "context": {},
            "idempotency_key": str(uuid.uuid4()),
        }

        logger.info(f"[N8N] Creating stream with payload: {payload}")

        return N8nLLMStream(
            self,
            chat_ctx,
            fnc_ctx,
            self.webhook_url,
            self.webhook_token,
            payload,
            self.timeout,
        )


class N8nLLMStream(LLMStream):
    """Stream implementation for n8n webhook responses"""

    def __init__(
        self,
        llm: N8nWebhookLLM,
        chat_ctx: ChatContext,
        fnc_ctx: Optional[Any],
        webhook_url: str,
        webhook_token: str,
        payload: dict,
        timeout: float,
    ):
        # LLMStream expects: llm, chat_ctx, tools, conn_options
        from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS

        super().__init__(
            llm,
            chat_ctx=chat_ctx,
            tools=[],  # No tools for now
            conn_options=DEFAULT_API_CONNECT_OPTIONS,
        )
        self.webhook_url = webhook_url
        self.webhook_token = webhook_token
        self.payload = payload
        self.timeout = timeout
        logger.debug(f"[N8N Stream] Initialized with URL: {webhook_url}")

    async def __aenter__(self):
        """Enter async context manager"""
        logger.debug("[N8N Stream] Entering async context manager")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager"""
        logger.debug(
            f"[N8N Stream] Exiting async context manager (exc_type: {exc_type})"
        )
        # Parent class handles task cleanup
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _run(self):
        """Required abstract method - delegates to _fetch_response"""
        await self._fetch_response()

    async def _fetch_response(self):
        """Fetch response from n8n webhook and emit chunks"""
        logger.info(f"[N8N Stream] Starting webhook call to {self.webhook_url}")
        logger.debug(f"[N8N Stream] Payload: {self.payload}")

        headers = {"Content-Type": "application/json"}

        if self.webhook_token:
            headers["Authorization"] = f"Bearer {self.webhook_token}"
            logger.debug("[N8N Stream] Added Bearer token to headers")

        try:
            logger.debug("[N8N Stream] Creating aiohttp session...")
            async with aiohttp.ClientSession() as session:
                logger.info(f"[N8N Stream] Sending POST request to webhook...")
                async with session.post(
                    self.webhook_url,
                    json=self.payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    logger.info(
                        f"[N8N Stream] Received response: status={response.status}"
                    )
                    if response.status == 200:
                        # Try to parse as JSON first, fall back to text
                        content_type = response.headers.get("content-type", "")

                        if "application/json" in content_type:
                            try:
                                data = await response.json()
                                logger.debug(f"[N8N Stream] Response data: {data}")
                                # Extract response text from various possible formats
                                if isinstance(data, dict):
                                    # Try different keys that n8n might use
                                    text = (
                                        data.get("output")
                                        or data.get("response")
                                        or data.get("text")
                                        or data.get("message")
                                        or ""
                                    )
                                    # If text is still a dict, try to extract text or set as empty
                                    if isinstance(text, dict):
                                        nested_text = text.get("text", "")
                                        # Only use string representation if there's actual content
                                        if nested_text and nested_text != "":
                                            text = nested_text
                                        else:
                                            text = ""
                                elif isinstance(data, str):
                                    text = data
                                else:
                                    text = str(data)
                            except json.JSONDecodeError:
                                # If JSON parsing fails, treat as text
                                text = await response.text()
                        else:
                            # Plain text response
                            text = await response.text()

                        # Ensure we have a string
                        text = str(text) if text else "I couldn't generate a response."
                        logger.info(f"[N8N Stream] Extracted text: {text[:100]}...")
                    else:
                        body = await response.text()
                        logger.error(
                            f"[N8N Stream] Webhook returned status {response.status}, body: {body}"
                        )
                        text = "I'm having trouble processing your request right now."

        except (asyncio.TimeoutError, aiohttp.ServerTimeoutError) as e:
            logger.error(f"[N8N Stream] Timeout after {self.timeout} seconds: {e}")
            text = "The request timed out. Please try again."
        except Exception as e:
            logger.error(f"[N8N Stream] Error calling webhook: {type(e).__name__}: {e}")
            import traceback

            logger.debug(f"[N8N Stream] Traceback: {traceback.format_exc()}")
            # Check if it's a timeout-related error
            if "timeout" in str(e).lower() or isinstance(e, TimeoutError):
                text = "The request timed out. Please try again."
            else:
                text = "I encountered an error. Please try again."

        # Create complete message for the chat context
        logger.debug(f"[N8N Stream] Setting cursor with text: {text[:50]}...")
        # ChatMessage expects content to be a list
        self._llm._cursors[self._chat_ctx] = ChatMessage(
            role="assistant", content=[text]
        )

        # Emit response in chunks for smoother TTS
        chunk_size = 50
        num_chunks = (len(text) + chunk_size - 1) // chunk_size
        logger.debug(
            f"[N8N Stream] Chunking response into {num_chunks} chunks of {chunk_size} chars"
        )

        for i in range(0, len(text), chunk_size):
            chunk_text = text[i : i + chunk_size]

            delta = ChoiceDelta(
                role="assistant",
                content=chunk_text,
            )

            chunk = ChatChunk(
                id=str(uuid.uuid4()),
                delta=delta,
            )

            logger.debug(
                f"[N8N Stream] Sending chunk {i//chunk_size + 1}/{num_chunks}: {chunk_text[:20]}..."
            )
            self._event_ch.send_nowait(chunk)
            await asyncio.sleep(0.02)  # Small delay for streaming effect

        # Signal completion
        logger.debug("[N8N Stream] All chunks sent, closing channel")
        self._event_ch.close()

    async def __anext__(self):
        """Async iteration for streaming"""
        try:
            chunk = await self._event_aiter.__anext__()
            logger.debug(
                f"[N8N Stream] Received chunk: {chunk.delta.content if chunk.delta else 'empty'}"
            )
            return chunk
        except StopAsyncIteration:
            logger.debug("[N8N Stream] Iteration complete")
            raise


def prewarm(proc: JobProcess):
    """Preload models for faster startup"""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    """Main entry point for the n8n agent"""

    # Set logging level to DEBUG for development
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(logging.DEBUG)

    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    logger.info("[N8N Agent] Starting n8n webhook agent")

    # Get n8n configuration from environment
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    webhook_token = os.getenv("N8N_WEBHOOK_TOKEN", "")  # Optional for testing

    if not webhook_url:
        logger.error("N8N_WEBHOOK_URL must be set")
        raise ValueError("Missing n8n webhook URL")

    logger.info(f"[N8N Agent] Webhook URL: {webhook_url}")
    logger.info(f"[N8N Agent] Token configured: {'Yes' if webhook_token else 'No'}")

    # Create custom n8n LLM
    n8n_llm = N8nWebhookLLM(
        webhook_url=webhook_url, webhook_token=webhook_token, timeout=8.0
    )
    logger.info("[N8N Agent] Created N8nWebhookLLM instance")

    # Set up voice AI pipeline with n8n webhook as the LLM
    session = AgentSession(
        llm=n8n_llm,
        stt=deepgram.STT(model="nova-3", language="multi"),
        # tts=cartesia.TTS(voice="6f84f4b8-58a2-430c-8c79-688dad597532"),
        tts=cartesia.TTS(voice="32b3f3c5-7171-46aa-abe7-b598964aa793"),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Handle false positive interruptions
    @session.on("agent_false_interruption")
    def _on_agent_false_interruption(ev: AgentFalseInterruptionEvent):
        logger.info("false positive interruption, resuming")
        session.generate_reply(instructions=ev.extra_instructions or NOT_GIVEN)

    # Metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start the session with a simple agent
    from livekit.agents import Agent

    agent = Agent(
        instructions="""You are a helpful voice assistant powered by n8n workflows.
        Keep responses concise and conversational."""
    )

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Connect to the room
    await ctx.connect()


# Export classes and functions for testing
__all__ = [
    "N8nWebhookLLM",
    "N8nLLMStream",
    "prewarm",
    "entrypoint",
    "Agent",
    "AgentSession",
]

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
