# Conversation Persistence Implementation

## Overview

This document describes the conversation persistence system for the medical agent, which stores conversation recordings and transcripts to Airtable via N8N webhooks.

## Architecture

The implementation follows SOLID principles with a clean separation of concerns:

```
src/
├── persistence/
│   ├── __init__.py                   # Factory function & exports
│   ├── interface.py                  # Abstract base class (DIP)
│   ├── n8n_persistence.py            # N8N webhook implementation
│   ├── test_persistence.py           # Test mode (local JSON)
│   └── conversation_recorder.py      # Real-time transcript capture
└── medical_agent.py                  # Integrated with persistence
```

### Design Principles

1. **Dependency Inversion**: `medical_agent.py` depends on the abstract `ConversationPersistence` interface, not concrete implementations
2. **Single Responsibility**: Each class has one job:
   - `ConversationRecorder`: Tracks transcript during conversation
   - `ConversationPersistence`: Defines storage contract
   - `N8nConversationPersistence`: Implements N8N webhook calls
   - `TestConversationPersistence`: Implements local JSON logging
3. **Open/Closed**: Easy to add new backends (Supabase, direct Airtable) without modifying existing code

## Data Model

### ConversationData

Maps to Airtable's "Conversations" table schema:

```python
@dataclass
class ConversationData:
    voice_agent_name: str           # "Camille"
    transcript: str                 # Full conversation with timestamps
    conversation_date: str          # ISO format: "2025-10-30"
    patient_name: Optional[str]     # Captured during call
    phone_number: Optional[str]     # Captured during call
    audio_recording_url: Optional[str]  # From LiveKit Egress (future)
    appointment_date: Optional[str] # If appointment booked
    appointment_time: Optional[str] # If appointment booked
    birth_date: Optional[str]       # For new patients
    reason: Optional[str]           # Reason for visit
```

## How It Works

### 1. Real-Time Transcript Capture

During the conversation, the `ConversationRecorder` captures:
- User messages (from `user_input_transcribed` events)
- Agent responses (from `conversation_item_added` events)
- Patient information (from `log_appointment_details` tool calls)
- Appointment information (from `log_appointment_details` tool calls)

Each message is logged to the console in real-time:

```
[Transcript] USER: Bonjour, je voudrais prendre rendez-vous.
[Transcript] AGENT: Bien sûr! Quel est votre nom complet?
```

**Important Note**: OpenAI Realtime API transcripts may have delays. User transcripts often arrive after the agent has already responded. This is a known limitation of the Realtime API.

### 2. Data Storage on Disconnect

When the conversation ends, the shutdown callback:
1. Builds the full transcript with timestamps
2. Collects patient and appointment info
3. Creates a `ConversationData` object
4. Stores via the persistence layer

### 3. N8N Webhook Endpoint

**New endpoint required**: `POST {base_url}/store_conversation`

**Payload format**:
```json
{
  "action": "store_conversation",
  "voice_agent_name": "Camille",
  "audio_recording_url": "https://...",
  "transcript": "[2025-10-30T14:23:45] AGENT: ...\n[2025-10-30T14:23:47] USER: ...",
  "conversation_date": "2025-10-30",
  "patient_name": "Jean Dupont",
  "phone_number": "01 23 45 67 89",
  "birth_date": "1980-05-15",
  "appointment_date": "2025-11-05",
  "appointment_time": "14:30",
  "reason": "Consultation générale"
}
```

**N8N workflow should**:
1. Upsert Patient record (find by phone_number)
2. Create/update Appointment record
3. Create Conversation record linked to Patient and Appointment

## Configuration

### Environment Variables

```bash
# Required for production mode
N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/your-webhook-id
N8N_WEBHOOK_TOKEN=your-webhook-bearer-token  # Optional

# Enable test mode (saves to local JSON instead of calling webhook)
TEST_MODE=true
```

### Test Mode

When `TEST_MODE=true`:
- Conversations saved to `logs/conversations/conversation_<timestamp>.json`
- No webhook calls are made
- Payloads logged to console with `[TEST MODE]` prefix

## Usage

### In Medical Agent

The persistence layer is already integrated into `medical_agent.py`:

```python
# Initialize (happens automatically in entrypoint)
recorder = ConversationRecorder(voice_agent_name="Camille")
persistence = create_persistence()

# Capture transcript (automatic via event handlers)
recorder.add_user_message("Bonjour...")
recorder.add_agent_message("Bonjour, cabinet du docteur Fillion...")

# Store on disconnect (automatic via shutdown callback)
data = ConversationData(...)
await persistence.store_conversation(data)
```

### Manual Testing

Run the test script:

```bash
python scripts/test_persistence.py
```

This tests:
- Conversation recorder
- Test mode persistence (local JSON)
- N8N persistence initialization
- Full integration

## Future Extensions

### Adding Supabase Backend

Create `src/persistence/supabase_persistence.py`:

```python
from .interface import ConversationPersistence

class SupabaseConversationPersistence(ConversationPersistence):
    async def store_conversation(self, data: ConversationData) -> bool:
        # Implement Supabase storage
        pass
```

Update `create_persistence()` in `__init__.py` to support Supabase mode.

**No changes needed in `medical_agent.py`** - it depends on the interface!

### Adding LiveKit Egress Recording

1. Configure LiveKit Egress to record room sessions
2. Set up webhook to receive `egress_ended` events
3. Extract `recording_url` from webhook payload
4. Pass to `ConversationData.audio_recording_url`

Example egress configuration:
```python
from livekit import api

# Start recording when agent connects
egress_client = api.EgressServiceClient()
await egress_client.start_room_composite_egress(
    room_name=ctx.room.name,
    audio_only=True,
    file_type="mp4",
    output=S3Upload(...)
)
```

## Error Handling

- **Webhook failures**: Logged but don't crash the agent
- **No retries**: Errors are logged, conversation continues
- **Missing data**: Optional fields can be `None`

## Logging

The system logs:
- `[Transcript] USER: ...` - User messages
- `[Transcript] AGENT: ...` - Agent responses
- `[Conversation] Summary: ...` - Conversation summary on disconnect
- `[N8N Persistence]` or `[TEST MODE]` - Storage operations

Set log level to `DEBUG` to see full transcripts:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Testing

### Unit Tests

```bash
python scripts/test_persistence.py
```

### Integration Test

1. Set `TEST_MODE=true` in `.env`
2. Run the medical agent
3. Have a test conversation
4. Check `logs/conversations/` for the JSON file
5. Verify all fields are captured correctly

### Production Test

1. Set `TEST_MODE=false`
2. Configure N8N webhook URL
3. Implement `store_conversation` endpoint in N8N
4. Run the agent and have a test conversation
5. Verify data appears in Airtable

## Notes

- **Agent name**: Hardcoded as `"Camille"` in `AGENT_NAME` constant
- **Recording URL**: Currently `None` - will be populated when LiveKit Egress is configured
- **Conversation outcome**: Not yet implemented - future enhancement
- **Transcript format**: Timestamped lines with speaker labels
