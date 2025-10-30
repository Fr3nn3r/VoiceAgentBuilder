# Audio Recording Implementation Guide

## Status: In Progress

### ✅ Completed

1. **AudioRecorder Class** ([src/persistence/audio_recorder.py](../src/persistence/audio_recorder.py))
   - Buffers audio frames from LiveKit room
   - Encodes to MP3 using ffmpeg
   - Memory-efficient design (< 50MB for 10min call)
   - Async operations with proper locking

2. **Updated Persistence Layer**
   - N8N persistence supports binary audio upload ([src/persistence/n8n_persistence.py](../src/persistence/n8n_persistence.py))
   - Test persistence saves MP3 files locally ([src/persistence/test_persistence.py](../src/persistence/test_persistence.py))
   - Interface updated with `audio_data` parameter

3. **Multipart Upload Support**
   - N8N endpoint receives: `metadata` (JSON) + `audio` (MP3 file)
   - Automatic fallback to JSON-only if no audio

### ⏳ Remaining Tasks

**1. Integrate AudioRecorder into medical_agent.py**
   - Create AudioRecorder instance on startup
   - Subscribe to room audio tracks
   - Capture audio frames during conversation
   - Encode to MP3 on disconnect
   - Pass MP3 data to persistence layer

**2. LiveKit Room Audio Capture**
   - Subscribe to mixed audio from room
   - Or subscribe to individual participant tracks
   - Feed frames to AudioRecorder

**3. Update Store Conversation Callback**
   - Encode audio after conversation ends
   - Pass MP3 bytes to `persistence.store_conversation()`

**4. Create N8N Webhook Documentation**
   - Document the multipart/form-data format
   - Provide N8N workflow template

**5. End-to-End Testing**
   - Test in TEST_MODE (saves local MP3)
   - Test with N8N webhook
   - Verify Airtable upload

## Implementation Code

### Integration into medical_agent.py

Add after persistence initialization (around line 397):

```python
from persistence.audio_recorder import AudioRecorder

# Initialize audio recorder
audio_recorder = AudioRecorder(sample_rate=16000, channels=1)
logger.info("[Config] Initialized audio recorder")
```

Subscribe to room audio after connection (around line 520):

```python
# Subscribe to room audio for recording
@ctx.room.on("track_subscribed")
def on_track_subscribed(track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
    """Capture audio tracks for recording"""
    async def handle_audio_track():
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"[Audio Recorder] Subscribed to audio track from {participant.identity}")

            # Start recording when first track arrives
            if not audio_recorder.is_recording:
                await audio_recorder.start_recording()

            # Capture audio frames
            async for frame in rtc.AudioStream(track):
                await audio_recorder.add_audio_frame(frame)

    asyncio.create_task(handle_audio_track())
```

Update store_conversation callback (around line 509):

```python
async def store_conversation():
    """Store conversation data on session end"""
    logger.info("[Conversation] Storing conversation data...")
    logger.info(f"[Conversation] Summary: {recorder.get_summary()}")

    # Stop recording
    await audio_recorder.stop_recording()

    # Get full transcript
    transcript = recorder.get_full_transcript()
    logger.debug(f"[Conversation] Full transcript:\n{transcript}")

    # Encode audio to MP3
    audio_data = None
    try:
        duration = audio_recorder.get_duration_seconds()
        if duration > 0:
            logger.info(f"[Conversation] Encoding {duration:.1f}s of audio to MP3...")
            audio_data = await audio_recorder.encode_to_mp3(bitrate="128k")
            logger.info(f"[Conversation] Encoded MP3: {len(audio_data) / 1024 / 1024:.2f}MB")
        else:
            logger.warning("[Conversation] No audio recorded")
    except Exception as e:
        logger.error(f"[Conversation] Failed to encode audio: {e}")
        audio_data = None  # Continue without audio

    # Build conversation data
    conversation_data = ConversationData(
        voice_agent_name=recorder.voice_agent_name,
        transcript=transcript,
        conversation_date=datetime.now(timezone.utc).date().isoformat(),
        patient_name=recorder.patient_name,
        phone_number=recorder.phone_number,
        birth_date=recorder.birth_date,
        reason=recorder.reason,
        appointment_date=recorder.appointment_date,
        appointment_time=recorder.appointment_time,
        audio_recording_url=None,  # Will be set by N8N after upload
    )

    # Store via persistence layer (with audio)
    success = await persistence.store_conversation(conversation_data, audio_data=audio_data)
    if success:
        logger.info("[Conversation] Successfully stored conversation data")
    else:
        logger.error("[Conversation] Failed to store conversation data")
```

## N8N Webhook Endpoint

### Expected Request Format

**With Audio**:
```
POST /store_conversation
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary...

----WebKitFormBoundary...
Content-Disposition: form-data; name="metadata"
Content-Type: application/json

{
  "action": "store_conversation",
  "voice_agent_name": "Camille",
  "transcript": "...",
  "conversation_date": "2025-10-30",
  "patient_name": "Jean Dupont",
  "phone_number": "01 23 45 67 89",
  ...
}
----WebKitFormBoundary...
Content-Disposition: form-data; name="audio"; filename="recording.mp3"
Content-Type: audio/mpeg

<binary MP3 data>
----WebKitFormBoundary...
```

**Without Audio** (fallback):
```
POST /store_conversation
Content-Type: application/json

{
  "action": "store_conversation",
  "voice_agent_name": "Camille",
  "transcript": "...",
  ...
}
```

### N8N Workflow Steps

1. **Webhook Trigger**
   - Listen for POST requests
   - Accept multipart/form-data

2. **Extract Metadata**
   - Parse JSON from `metadata` field
   - Extract conversation details

3. **Handle Audio File**
   - Get binary data from `audio` field
   - Upload to Airtable attachment field

4. **Upsert to Airtable**
   - Find/create Patient record (by phone_number)
   - Create/update Appointment record
   - Create Conversation record with:
     - Transcript
     - Audio attachment
     - Linked to Patient and Appointment

5. **Return Success**
   - Send 200 OK with conversation ID

## Testing

### Test in TEST_MODE

```bash
$env:TEST_MODE="true"
$env:LOG_LEVEL="INFO"
uv run python .\src\medical_agent.py dev
```

Expected output:
```
[Audio Recorder] Initialized
[Audio Recorder] Subscribed to audio track from responsive-vector
[Audio Recorder] Started recording
... conversation happens ...
[Audio Recorder] Stopped recording (1234 frames)
[Conversation] Encoding 125.4s of audio to MP3...
[Audio Recorder] Encoded MP3: 1.92MB
[TEST MODE] Saved audio to logs\conversations\conversation_20251030_160000.mp3
[TEST MODE] Saved conversation to logs\conversations\conversation_20251030_160000.json
```

Check files:
- `logs/conversations/conversation_YYYYMMDD_HHMMSS.json` - Metadata with `audio_file_local` field
- `logs/conversations/conversation_YYYYMMDD_HHMMSS.mp3` - Playable MP3 file

### Test with N8N

```bash
$env:TEST_MODE="false"
$env:N8N_WEBHOOK_URL="https://your-n8n-instance.com/webhook"
uv run python .\src\medical_agent.py dev
```

Expected:
- Agent sends multipart/form-data to N8N
- N8N uploads MP3 to Airtable
- Conversation record created with audio attachment

## Troubleshooting

### No Audio Captured

**Symptom**: `No audio recorded` warning

**Causes**:
1. Audio tracks not subscribed
2. No audio frames received
3. Participant disconnected before audio started

**Solution**: Check logs for `Subscribed to audio track` message

### ffmpeg Not Found

**Symptom**: `ffmpeg encoding failed: FileNotFoundError`

**Solution**:
```bash
# Install ffmpeg
# Windows (Chocolatey): choco install ffmpeg
# Windows (Scoop): scoop install ffmpeg
# Verify: ffmpeg -version
```

### MP3 File Too Large

**Symptom**: N8N timeout or upload failure

**Solutions**:
1. Lower bitrate: `encode_to_mp3(bitrate="96k")`
2. Increase N8N timeout
3. Check Airtable attachment size limit (20MB max)

### Memory Usage High

**Symptom**: Agent uses > 100MB RAM

**Cause**: Long conversation with high-quality audio

**Solutions**:
1. Lower sample rate: `AudioRecorder(sample_rate=8000)` (phone quality)
2. Add periodic buffer clearing for very long calls
3. Stream to disk instead of memory (future enhancement)

## Future Enhancements

1. **Streaming to Disk**
   - For calls > 15 minutes
   - Write frames directly to temp file
   - Reduces memory usage

2. **Parallel Encoding**
   - Don't block disconnect on MP3 encoding
   - Encode in background, upload separately

3. **Compression Options**
   - Variable bitrate (VBR)
   - Opus codec (smaller files)
   - Automatic bitrate based on duration

4. **Direct Airtable Upload**
   - Skip N8N for audio
   - Upload directly to Airtable API
   - Requires Airtable API key

## Summary

**Architecture**:
```
LiveKit Room
    ↓
Audio Tracks
    ↓
AudioRecorder (buffers frames)
    ↓
ffmpeg (encodes to MP3)
    ↓
N8N Webhook (multipart/form-data)
    ↓
Airtable (Conversations table)
```

**Files Modified**:
- ✅ `src/persistence/audio_recorder.py` (new)
- ✅ `src/persistence/interface.py` (updated)
- ✅ `src/persistence/n8n_persistence.py` (updated)
- ✅ `src/persistence/test_persistence.py` (updated)
- ⏳ `src/medical_agent.py` (needs integration code above)

**Ready for**: Integration into medical_agent.py and testing
