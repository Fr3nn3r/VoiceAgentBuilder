"""Basic test to verify n8n_agent functionality"""
import pytest
from n8n_agent import N8nWebhookLLM


def test_n8n_webhook_llm_initialization():
    """Test basic initialization of N8nWebhookLLM"""
    llm = N8nWebhookLLM(
        webhook_url="https://test.webhook.com/endpoint",
        webhook_token="test_token",
        timeout=10.0
    )

    assert llm.webhook_url == "https://test.webhook.com/endpoint"
    assert llm.webhook_token == "test_token"
    assert llm.timeout == 10.0
    assert llm.turn_counter == 0
    assert isinstance(llm.session_id, str)
    print(f"✓ Basic initialization test passed")