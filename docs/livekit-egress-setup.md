# LiveKit Egress Setup for Call Recordings

## Overview

This guide explains how to configure LiveKit Egress to automatically record voice agent conversations and capture the recording URLs for storage in Airtable.

## Prerequisites

- **LiveKit Cloud account** (Egress is pre-configured and ready to use)
- **Cloud storage** (S3, Google Cloud Storage, or Azure Blob Storage)
- **API access token** with `roomRecord` permission

## Step 1: Configure Cloud Storage

### Option A: AWS S3

1. Create an S3 bucket for recordings (e.g., `dr-fillion-recordings`)
2. Create IAM credentials with write access to the bucket
3. Note down:
   - Access Key ID
   - Secret Access Key
   - Bucket name
   - Region (e.g., `us-east-1`)

### Option B: Google Cloud Storage

1. Create a GCS bucket
2. Create a service account with Storage Object Creator role
3. Download the credentials JSON file
4. Note down bucket name

### Option C: Azure Blob Storage

1. Create a storage account and container
2. Get the account name and access key
3. Note down container name

## Step 2: Start Recording via API

### Python Example (using LiveKit SDK)

```python
from livekit import api
import os

# Initialize LiveKit API (SDK v1.0+)
lkapi = api.LiveKitAPI(
    url=os.getenv("LIVEKIT_URL"),
    api_key=os.getenv("LIVEKIT_API_KEY"),
    api_secret=os.getenv("LIVEKIT_API_SECRET"),
)
egress = lkapi.egress

# Configure recording request
request = api.RoomCompositeEgressRequest(
    room_name="camille",  # Your room name
    audio_only=True,
    file_outputs=[
        api.EncodedFileOutput(
            file_type=api.EncodedFileType.MP4,  # MP4 container for audio
            filepath="recordings/{room_name}-{time}.mp4",
            s3=api.S3Upload(
                access_key=os.getenv("AWS_ACCESS_KEY"),
                secret=os.getenv("AWS_SECRET_KEY"),
                bucket="dr-fillion-recordings",
                region="us-east-1",
            ),
        )
    ],
)

# Start audio-only room recording
response = await egress.start_room_composite_egress(request)

egress_id = response.egress_id
print(f"Recording started: {egress_id}")
```

### When to Start Recording

**Option 1: On participant join** (recommended)
- Use LiveKit webhook `participant_joined` event
- Automatically start egress when first participant joins

**Option 2: In agent code** (manual)
- Start recording in the agent's `entrypoint()` function
- Store `egress_id` for later reference

## Step 3: Configure Webhooks

### Set Up Webhook Endpoint

Create an endpoint to receive egress lifecycle events:

```
POST https://your-n8n-instance.com/webhook/egress_events
```

### Webhook Events

LiveKit sends webhooks for:
- `egress_started`: Recording has started
- `egress_updated`: Recording progress update
- `egress_ended`: Recording completed and uploaded

### Egress Ended Event Payload

```json
{
  "event": "egress_ended",
  "egressInfo": {
    "egress_id": "EG_abc123",
    "room_id": "RM_xyz789",
    "room_name": "camille",
    "status": "EGRESS_COMPLETE",
    "file_results": [
      {
        "filename": "recordings/camille-20251030-150000.mp4",
        "size": 1234567,
        "duration": 123.45,
        "download_url": "https://s3.amazonaws.com/dr-fillion-recordings/recordings/camille-20251030-150000.mp4"
      }
    ],
    "started_at": 1698765000000,
    "ended_at": 1698765123000
  }
}
```

### Extract Recording URL

From the webhook payload:
```python
recording_url = event["egressInfo"]["file_results"][0]["download_url"]
```

## Step 4: Configure LiveKit Cloud Console

1. Go to your LiveKit Cloud project
2. Navigate to **Settings > Webhooks**
3. Add webhook URL: `https://your-n8n-instance.com/webhook/egress_events`
4. Select events: `egress_ended`
5. Copy the signing key for webhook verification

## Step 5: Integrate with Medical Agent

### Update Environment Variables

```bash
# Add to .env
AWS_ACCESS_KEY=your-access-key
AWS_SECRET_KEY=your-secret-key
AWS_BUCKET=dr-fillion-recordings
AWS_REGION=us-east-1

# Or for Google Cloud Storage
GCP_CREDENTIALS_JSON={"type":"service_account",...}
GCP_BUCKET=your-bucket-name
```

### Modify medical_agent.py

Add egress initialization in `entrypoint()`:

```python
async def entrypoint(ctx: JobContext):
    # ... existing setup ...

    # Store egress_id in context for later reference
    egress_id = None

    # Start recording when agent connects
    async def start_recording():
        nonlocal egress_id
        try:
            # Initialize LiveKit API (SDK v1.0+)
            lkapi = api.LiveKitAPI(
                url=os.getenv("LIVEKIT_URL"),
                api_key=os.getenv("LIVEKIT_API_KEY"),
                api_secret=os.getenv("LIVEKIT_API_SECRET"),
            )
            egress = lkapi.egress

            # Configure recording request
            request = api.RoomCompositeEgressRequest(
                room_name=ctx.room.name,
                audio_only=True,
                file_outputs=[
                    api.EncodedFileOutput(
                        file_type=api.EncodedFileType.MP4,
                        filepath=f"recordings/{ctx.room.name}-{{time}}.mp4",
                        s3=api.S3Upload(
                            access_key=os.getenv("AWS_ACCESS_KEY"),
                            secret=os.getenv("AWS_SECRET_KEY"),
                            bucket=os.getenv("AWS_BUCKET"),
                            region=os.getenv("AWS_REGION"),
                        ),
                    )
                ],
            )

            response = await egress.start_room_composite_egress(request)
            egress_id = response.egress_id
            logger.info(f"[Recording] Started egress: {egress_id}")
        except Exception as e:
            logger.error(f"[Recording] Failed to start egress: {e}")

    # Start recording after connection
    await ctx.connect()
    await start_recording()

    # ... rest of agent code ...
```

## Step 6: Handle Recording URL in N8N

### Create N8N Workflow

**Trigger**: Webhook node listening for egress events

**Workflow steps**:
1. Receive egress webhook
2. Filter for `egress_ended` events
3. Extract `download_url` from `file_results[0]`
4. Match `room_name` to conversation record in Airtable
5. Update Conversation record with `audio_recording_url`

### N8N Webhook Example

```javascript
// N8N Function node to extract recording URL
const event = $input.all()[0].json;

if (event.event === "egress_ended") {
  const fileResult = event.egressInfo.file_results[0];

  return {
    room_name: event.egressInfo.room_name,
    recording_url: fileResult.download_url,
    duration: fileResult.duration,
    file_size: fileResult.size,
    started_at: new Date(event.egressInfo.started_at),
    ended_at: new Date(event.egressInfo.ended_at),
  };
}
```

## Alternative: Room-Level Auto-Recording

### LiveKit Cloud Console Configuration

1. Navigate to **Settings > Recording**
2. Enable **Auto-record all rooms**
3. Configure storage destination (S3/GCS/Azure)
4. Set file naming template: `recordings/{room_name}-{time}.mp4`
5. Enable audio-only mode

**Pros**:
- No code changes needed
- Automatically records every session
- Webhook notifications included

**Cons**:
- Records even test/debugging sessions
- Less control over start/stop timing

## Step 7: Update Persistence Layer

The medical agent already has a placeholder for recording URLs. When egress webhooks are configured, the URL will be automatically available in the conversation data.

No code changes needed - the `audio_recording_url` field is already in place!

## Troubleshooting

### Recording Not Starting

- Verify API token has `roomRecord` permission
- Check egress logs in LiveKit Cloud console
- Ensure cloud storage credentials are correct

### No Webhook Received

- Verify webhook URL is publicly accessible
- Check webhook signing key configuration
- Review webhook delivery logs in LiveKit console

### Recording URL Not Available

- Ensure `egress_ended` webhook is configured
- Check that recording completed successfully
- Verify storage upload succeeded

## Cost Considerations

- **LiveKit Cloud**: Egress usage billed per minute
- **Storage**: S3/GCS/Azure storage costs for MP4 files
- **Bandwidth**: Download costs when accessing recordings

Typical 30-minute call ≈ 5-10MB audio-only MP4

## Security Best Practices

1. Use IAM roles with minimal permissions (write-only to recordings bucket)
2. Enable bucket versioning for backup
3. Set lifecycle policies to archive old recordings
4. Encrypt recordings at rest (S3: SSE-S3 or SSE-KMS)
5. Use signed URLs for time-limited access to recordings
6. Verify webhook signatures to prevent spoofing

## Summary

**Required steps**:
1. ✅ Set up cloud storage (S3/GCS/Azure)
2. ✅ Configure LiveKit webhooks for `egress_ended` events
3. ✅ Create N8N workflow to capture recording URLs
4. ✅ Link recording URL to conversation in Airtable

**Optional (for automatic recording)**:
- Enable auto-recording in LiveKit Cloud console

**Already implemented**:
- ✅ `audio_recording_url` field in persistence layer
- ✅ Conversation data structure ready for URLs
- ✅ Error handling for missing URLs

The medical agent will work with or without recordings - the `audio_recording_url` will simply be `null` until egress is configured.
