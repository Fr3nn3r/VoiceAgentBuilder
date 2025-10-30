# Transcript Capture Debugging Guide

## Current Status

**User transcripts**: ✅ Working (captured via `user_input_transcribed` event)

**Agent transcripts**: ❌ Not working - `conversation_item_added` event not firing or not capturing text

## Quick Test

Run a test conversation with debug logging enabled:

```bash
# Set debug logging
export LOG_LEVEL=DEBUG  # Linux/Mac
set LOG_LEVEL=DEBUG     # Windows CMD
$env:LOG_LEVEL="DEBUG"  # Windows PowerShell

# Run agent
uv run python src/medical_agent.py dev
```

## What to Look For in Logs

### ✅ Expected Logs (If Working)

```
[Event] conversation_item_added event fired
[Event] Item role: assistant
[Event] Captured assistant message (123 chars)
[Transcript] AGENT: Bonjour, cabinet du docteur Fillion...
```

### ❌ Problem Indicators

**Event never fires**:
```
# You see user transcripts but NO conversation_item_added logs at all
[Transcript] USER: Bonjour...
[Transcript] USER: Je m'appelle Frédéric...
# ← No [Event] logs appear
```

**Event fires but no text**:
```
[Event] conversation_item_added event fired
[Event] Item role: assistant
[Event] Assistant item found but no text extracted
[Event] Item content type: <class 'NoneType'>
```

**Event fires with wrong role**:
```
[Event] conversation_item_added event fired
[Event] Item role: user  # ← Should be "assistant" for agent messages
```

## Troubleshooting Steps

### Step 1: Verify Event is Registered

Check that the event handler is registered:

```python
# In medical_agent.py, after session creation
@session.on("conversation_item_added")
def on_conversation_item(ev: Any):
    logger.info("[Event] conversation_item_added event fired")
    # ... rest of handler
```

Look for this line in logs on startup:
```
[Config] Created 3 scheduling tools
```

The handler should be registered before `session.start()`.

### Step 2: Check OpenAI Realtime API Configuration

Verify modalities include "text":

```python
llm=openai.realtime.RealtimeModel(
    model="gpt-4o-realtime-preview-2024-12-17",
    voice="alloy",
    temperature=0.8,
    modalities=["audio", "text"],  # ← MUST include "text"
    turn_detection=TurnDetection(
        type="server_vad",
        create_response=True,  # ← MUST be True
    ),
)
```

### Step 3: Alternative Event Names

If `conversation_item_added` doesn't work, try these alternatives:

```python
# Try all of these and see which fires
@session.on("agent_response")
def on_agent_response(ev):
    logger.info(f"[Event] agent_response fired: {ev}")

@session.on("agent_speech_created")
def on_agent_speech_created(ev):
    logger.info(f"[Event] agent_speech_created fired: {ev}")

@session.on("response_created")
def on_response_created(ev):
    logger.info(f"[Event] response_created fired: {ev}")

@session.on("response_done")
def on_response_done(ev):
    logger.info(f"[Event] response_done fired: {ev}")
```

### Step 4: Inspect All Events

Log ALL session events to see what's available:

```python
# Add this temporarily to see all events
_original_emit = session._event_emitter.emit

def _debug_emit(event_name, *args, **kwargs):
    logger.info(f"[DEBUG] Event emitted: {event_name}")
    return _original_emit(event_name, *args, **kwargs)

session._event_emitter.emit = _debug_emit
```

### Step 5: Check LiveKit SDK Version

Verify you're using the latest LiveKit agents SDK:

```bash
uv pip list | grep livekit
```

Expected:
```
livekit-agents >= 1.2.9
livekit-plugins-openai >= [latest version]
```

Upgrade if needed:
```bash
uv pip install --upgrade livekit-agents livekit-plugins-openai
```

## Alternative Approaches

If `conversation_item_added` still doesn't work, here are fallback options:

### Option A: Hook into OpenAI Realtime Response Stream

Directly access the Realtime API response objects:

```python
# Access underlying RealtimeModel instance
realtime_model = session._llm

# Hook into response handler
original_handle_response = realtime_model._handle_response

async def custom_handle_response(response):
    # Extract text from response
    if hasattr(response, "output"):
        for output in response.output:
            if hasattr(output, "text"):
                recorder.add_agent_message(output.text)

    return await original_handle_response(response)

realtime_model._handle_response = custom_handle_response
```

### Option B: Capture via TTS Input

Agent text MUST be sent to TTS before audio generation. Hook into that flow:

```python
# The text goes to TTS - capture it there
original_say = session.say

async def custom_say(text, **kwargs):
    recorder.add_agent_message(text)
    return await original_say(text, **kwargs)

session.say = custom_say
```

### Option C: Use Separate STT for Transcription

Add a separate STT plugin that transcribes the agent's audio output:

```python
from livekit.plugins import deepgram

# Create separate STT for agent audio
agent_stt = deepgram.STT(model="nova-3", language="fr")

# Subscribe to agent audio track and transcribe
@ctx.room.on("track_published")
async def on_track(track, participant):
    if participant.identity == "agent":
        # Transcribe agent's audio
        async for result in agent_stt.recognize(track):
            recorder.add_agent_message(result.text)
```

## Expected Behavior

Once working, you should see:

```
[Transcript] USER: Je veux prendre rendez-vous
[Transcript] AGENT: Bien sûr! Quel est votre nom complet?
[Transcript] USER: Frédéric Brunner
[Transcript] AGENT: Merci Frédéric. Quel est votre numéro de téléphone?
```

And in the final JSON:

```json
{
  "transcript": "[2025-10-30T15:17:06] USER: Je veux prendre rendez-vous\n[2025-10-30T15:17:07] AGENT: Bien sûr! Quel est votre nom complet?\n..."
}
```

## Debug Checklist

- [ ] `LOG_LEVEL=DEBUG` set in environment
- [ ] User transcripts appear (`[Transcript] USER:`)
- [ ] `[Event] conversation_item_added event fired` logs appear
- [ ] Item role is "assistant"
- [ ] Item has text content
- [ ] `[Transcript] AGENT:` logs appear
- [ ] Full transcript shows both USER and AGENT in final JSON

## Next Steps

1. **Run test with DEBUG logging**
2. **Check logs for `[Event]` messages**
3. **If no events fire**: Try alternative event names (Step 3)
4. **If events fire but no text**: Check content structure (Step 4)
5. **If nothing works**: Use fallback Option B or C

## Getting Help

If issues persist, provide these details:

1. Full logs with `LOG_LEVEL=DEBUG`
2. Output of `uv pip list | grep livekit`
3. Contents of final JSON from `logs/conversations/`
4. Specific error messages or warnings

This will help diagnose whether it's:
- Event configuration issue
- SDK version compatibility
- OpenAI Realtime API behavior
- Data structure mismatch
