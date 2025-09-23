"""Shared fixtures and test configuration for n8n_agent tests"""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from livekit.agents.llm import ChatContext, ChatMessage, ChoiceDelta


@pytest.fixture
def mock_chat_context():
    """Create a mock ChatContext with test messages"""
    messages = [
        ChatMessage(role="system", content=["You are a helpful assistant"]),
        ChatMessage(role="user", content=["Hello, how are you?"]),
    ]
    ctx = ChatContext(items=messages)
    return ctx


@pytest.fixture
def mock_chat_context_empty():
    """Create an empty ChatContext"""
    return ChatContext(items=[])


@pytest.fixture
def mock_chat_context_complex():
    """Create a ChatContext with complex message structure"""
    messages = [
        ChatMessage(role="user", content=["What is the weather?"]),
        ChatMessage(role="assistant", content=["I can help you check the weather"]),
        ChatMessage(role="user", content=["Tell me about AI"]),
    ]
    return ChatContext(items=messages)


@pytest.fixture
def mock_webhook_url():
    """Provide a test webhook URL"""
    return "https://test.n8n.local/webhook/test"


@pytest.fixture
def mock_webhook_token():
    """Provide a test webhook token"""
    return "test_token_12345"


@pytest.fixture
def mock_session_id():
    """Provide a consistent session ID for testing"""
    return "test-session-" + str(uuid.uuid4())


@pytest.fixture
def sample_n8n_response():
    """Sample response from n8n webhook"""
    return {
        "output": "This is a test response from n8n"
    }


@pytest.fixture
def sample_n8n_response_complex():
    """Complex response structure from n8n"""
    return {
        "output": {
            "text": "Complex nested response",
            "metadata": {"confidence": 0.95}
        }
    }


@pytest.fixture
def sample_n8n_response_alternative_keys():
    """Response with alternative key names"""
    return {
        "response": "Response using 'response' key",
        "text": "Should not be used",  # 'response' has priority
    }


@pytest.fixture
def mock_vad():
    """Mock VAD for testing"""
    vad = MagicMock()
    vad.load = MagicMock(return_value=vad)
    return vad


@pytest.fixture
def mock_agent_session():
    """Mock AgentSession for testing"""
    session = AsyncMock()
    session.on = MagicMock()
    session.generate_reply = AsyncMock()
    session.start = AsyncMock()
    return session


@pytest.fixture
def mock_job_context():
    """Mock JobContext for testing"""
    ctx = MagicMock()
    ctx.room = MagicMock()
    ctx.room.name = "test_room"
    ctx.log_context_fields = {}
    ctx.add_shutdown_callback = MagicMock()
    ctx.connect = AsyncMock()
    ctx.proc = MagicMock()
    ctx.proc.userdata = {}
    ctx.inference_executor = MagicMock()  # Add inference_executor
    return ctx


@pytest.fixture
def mock_livekit_imports(mocker):
    """Mock all LiveKit imports"""
    # Mock all the LiveKit modules
    mocker.patch("livekit.agents.AgentSession", return_value=AsyncMock())
    mocker.patch("livekit.agents.Agent", return_value=MagicMock())
    mocker.patch("livekit.plugins.deepgram.STT", return_value=MagicMock())
    mocker.patch("livekit.plugins.cartesia.TTS", return_value=MagicMock())
    mocker.patch("livekit.plugins.turn_detector.multilingual.MultilingualModel", return_value=MagicMock())
    mocker.patch("livekit.plugins.noise_cancellation.BVC", return_value=MagicMock())
    mocker.patch("livekit.plugins.silero.VAD.load", return_value=MagicMock())


@pytest.fixture
async def mock_aiohttp_session(aioresponses):
    """Mock aiohttp session for webhook calls"""
    return aioresponses