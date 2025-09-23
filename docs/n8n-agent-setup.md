# n8n Voice Agent Setup

This document explains how to use the n8n webhook-based voice agent as an alternative to the OpenAI-based agent.

## Architecture

The n8n agent follows this flow:
1. **Speech-to-Text (STT)**: User speech → Deepgram → Text
2. **Processing**: Text → n8n webhook → LLM response (handled in n8n)
3. **Text-to-Speech (TTS)**: Response text → Cartesia → Audio
4. **Voice Loop**: LiveKit manages the real-time voice communication

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# n8n webhook configuration
N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/your-webhook-id
N8N_WEBHOOK_TOKEN=your-webhook-bearer-token

# STT/TTS providers (same as original agent)
DEEPGRAM_API_KEY=your-deepgram-key
CARTESIA_API_KEY=your-cartesia-key

# LiveKit configuration
LIVEKIT_URL=your-livekit-url
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
```

### n8n Workflow Setup

Your n8n workflow should:

1. **Accept webhook requests** with this format:
```json
{
  "session_id": "unique-session-id",
  "turn_id": "t_1",
  "input": {
    "type": "text",
    "text": "User's transcribed speech"
  },
  "context": {},
  "idempotency_key": "uuid-v4"
}
```

2. **Return responses** in one of these formats:
```json
// Option 1: response field
{"response": "Agent's response text"}

// Option 2: text field
{"text": "Agent's response text"}

// Option 3: Any JSON (will be stringified)
{"any": "data", "will": "work"}
```

3. **Handle authentication**: Validate the Bearer token from the `Authorization` header

4. **Respond within 8 seconds**: The webhook has an 8-second timeout

## Usage

### Running the Agent

```bash
# Run the n8n agent
python src/n8n_agent.py

# Or with LiveKit CLI
livekit-cli run-agent --url <livekit-url> src/n8n_agent.py
```

### Testing the Webhook

Test your n8n webhook independently:

```bash
python scripts/test_n8n_webhook.py
```

This will:
- Verify environment variables are set
- Send a test request to your n8n webhook
- Display the response
- Test the LLM class integration

## Key Differences from Original Agent

| Feature | Original (agent.py) | n8n (n8n_agent.py) |
|---------|-------------------|-------------------|
| LLM | OpenAI API | n8n webhook → Your LLM |
| History | Managed locally | Managed by n8n |
| Streaming | Native OpenAI streaming | Simulated chunking |
| Timeout | OpenAI default | 8 seconds |
| Auth | OpenAI API key | Bearer token |

## Troubleshooting

### Common Issues

1. **Timeout errors**: Ensure your n8n workflow responds within 8 seconds
2. **Auth errors**: Check your Bearer token is correct
3. **No response**: Verify your n8n workflow returns `response` or `text` field
4. **Connection refused**: Check N8N_WEBHOOK_URL is accessible

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Example n8n Workflow

A simple n8n workflow might:
1. Receive webhook
2. Call OpenAI/Claude/Local LLM
3. Add context (database lookups, etc.)
4. Return response

Benefits of this approach:
- **Flexibility**: Use any LLM or multiple LLMs
- **Control**: Add business logic, rate limiting, logging
- **Integration**: Connect to databases, APIs, services
- **Visual**: Build and modify flows visually in n8n

## Performance Considerations

- **Latency**: Additional network hop adds ~50-200ms
- **Timeout**: 8-second hard limit for responses
- **Streaming**: Responses are chunked for smoother TTS
- **Concurrency**: Each session maintains its own webhook connection