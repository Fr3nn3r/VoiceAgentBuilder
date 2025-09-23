"""
Test script for n8n webhook integration
Tests the webhook directly without LiveKit to validate the integration
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import aiohttp
import uuid
from dotenv import load_dotenv

load_dotenv()


async def test_webhook():
    """Test the n8n webhook with a sample request"""

    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    webhook_token = os.getenv("N8N_WEBHOOK_TOKEN")

    if not webhook_url or not webhook_token:
        print("[ERROR] N8N_WEBHOOK_URL and N8N_WEBHOOK_TOKEN must be set in .env file")
        return

    print(f"[OK] Testing n8n webhook")
    print(f"[OK] URL: {webhook_url}")
    print(f"[OK] Token: {'*' * 10}...")

    # Test payload matching the expected format
    payload = {
        "session_id": f"test_{uuid.uuid4()}",
        "turn_id": "t_1",
        "input": {
            "type": "text",
            "text": "Hello, this is a test message from the voice agent"
        },
        "context": {
            "test_mode": True,
            "lang": "en"
        },
        "idempotency_key": str(uuid.uuid4())
    }

    headers = {
        "Authorization": f"Bearer {webhook_token}",
        "Content-Type": "application/json"
    }

    print(f"\n[OK] Sending test request...")
    print(f"    Payload: {payload}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=8.0)
            ) as response:
                print(f"\n[OK] Response Status: {response.status}")

                if response.status == 200:
                    data = await response.json()
                    print(f"[OK] Response Data: {data}")

                    # Check expected response format
                    if isinstance(data, dict):
                        response_text = data.get("response") or data.get("text")
                        if response_text:
                            print(f"[OK] Extracted text: {response_text}")
                        else:
                            print(f"[X] No 'response' or 'text' field in response")
                    else:
                        print(f"[OK] Raw response: {data}")
                else:
                    error_text = await response.text()
                    print(f"[X] Error response: {error_text}")

    except aiohttp.ClientTimeout:
        print(f"[X] Request timed out after 8 seconds")
    except Exception as e:
        print(f"[X] Error: {e}")


async def test_n8n_llm_class():
    """Test the N8nWebhookLLM class directly"""
    from n8n_agent import N8nWebhookLLM
    from livekit.agents.llm import ChatContext, ChatMessage

    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    webhook_token = os.getenv("N8N_WEBHOOK_TOKEN")

    if not webhook_url or not webhook_token:
        print("[ERROR] Missing webhook configuration")
        return

    print("\n[OK] Testing N8nWebhookLLM class...")

    # Create LLM instance
    llm = N8nWebhookLLM(webhook_url, webhook_token)

    # Create chat context with a test message
    messages = [
        ChatMessage(role="user", content=["What is the weather today?"])
    ]
    chat_ctx = ChatContext(messages=messages)

    # Get a stream response
    stream = await llm.chat(chat_ctx)

    print("[OK] Streaming response:")
    full_response = ""
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].content:
            content = chunk.choices[0].content
            print(content, end="", flush=True)
            full_response += content

    print(f"\n\n[OK] Full response received: {len(full_response)} characters")


async def main():
    """Run all tests"""
    print("="*50)
    print("N8N WEBHOOK TEST")
    print("="*50)

    # Test 1: Direct webhook test
    await test_webhook()

    # Test 2: Test LLM class
    await test_n8n_llm_class()

    print("\n" + "="*50)
    print("TEST COMPLETE")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(main())