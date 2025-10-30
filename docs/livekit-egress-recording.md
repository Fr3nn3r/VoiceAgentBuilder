# LiveKit Egress Recording Setup

## Overview

We're using LiveKit Egress to record room audio server-side. This captures the mixed audio (both user and agent voices) professionally without local frame synchronization issues.

## Architecture

```
LiveKit Room → Egress Service → S3/R2 Storage → Webhook → N8N → Airtable
```

1. **Room starts** → Start Egress room composite recording
2. **Conversation happens** → Audio is recorded server-side
3. **Room ends** → Egress uploads MP3 to S3/R2
4. **Egress webhook fires** → Notifies our system with recording URL
5. **N8N receives data** → Updates Airtable with transcript + recording URL

## Storage Options

### Option 1: Cloudflare R2 (Recommended)
- **Cost**: Free tier: 10GB storage, 10M Class A operations/month
- **Egress**: Free (no egress fees unlike S3)
- **S3-compatible**: Works with LiveKit's S3 integration
- **Setup time**: 15 minutes

### Option 2: AWS S3
- **Cost**: ~$0.023/GB/month + egress fees
- **Native support**: Direct LiveKit integration
- **Setup time**: 10 minutes

### Option 3: Backblaze B2
- **Cost**: $0.005/GB/month (cheaper than S3)
- **S3-compatible**: Works with LiveKit
- **Setup time**: 15 minutes

## Implementation Steps

### 1. Configure Storage (Cloudflare R2)

**Create R2 Bucket:**
```bash
# Via Cloudflare Dashboard:
1. Go to R2 → Create bucket
2. Name: "voice-agent-recordings"
3. Location: Auto
```

**Create API Token:**
```bash
# R2 → Manage R2 API Tokens → Create API Token
- Name: "livekit-egress"
- Permissions: Object Read & Write
- Copy: Access Key ID, Secret Access Key
```

**Get S3 Endpoint:**
```
https://<account-id>.r2.cloudflarestorage.com
```

### 2. Configure Environment Variables

```bash
# .env
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_secret
LIVEKIT_URL=wss://your-project.livekit.cloud

# Storage (R2)
S3_ACCESS_KEY=<r2_access_key>
S3_SECRET_KEY=<r2_secret_key>
S3_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
S3_BUCKET=voice-agent-recordings
S3_REGION=auto

# Egress Webhook (optional - for notifications)
EGRESS_WEBHOOK_URL=https://your-n8n.com/webhook/egress-complete
```

### 3. Implementation Code

**Start recording when room connects:**

```python
from livekit import api

async def start_room_recording(room_name: str, room_id: str):
    """Start LiveKit Egress room composite recording"""

    # Initialize LiveKit API (SDK v1.0+)
    lkapi = api.LiveKitAPI(
        LIVEKIT_URL,
        LIVEKIT_API_KEY,
        LIVEKIT_API_SECRET
    )
    egress = lkapi.egress

    # Configure S3 upload
    s3_upload = api.S3Upload(
        access_key=S3_ACCESS_KEY,
        secret=S3_SECRET_KEY,
        region=S3_REGION,
        endpoint=S3_ENDPOINT,
        bucket=S3_BUCKET,
    )

    # Configure audio-only recording
    request = api.RoomCompositeEgressRequest(
        room_name=room_name,
        audio_only=True,
        file_outputs=[
            api.EncodedFileOutput(
                file_type=api.EncodedFileType.MP3,
                filepath=f"recordings/{room_id}.mp3",
                s3=s3_upload,
            )
        ],
    )

    # Start recording
    egress_info = await egress.start_room_composite_egress(request)

    logger.info(f"[Egress] Started recording {egress_info.egress_id} for room {room_name}")

    return egress_info.egress_id
```

**Stop recording (optional - auto-stops when room ends):**

```python
async def stop_room_recording(egress_id: str):
    """Stop LiveKit Egress recording"""

    # Initialize LiveKit API (SDK v1.0+)
    lkapi = api.LiveKitAPI(
        LIVEKIT_URL,
        LIVEKIT_API_KEY,
        LIVEKIT_API_SECRET
    )
    egress = lkapi.egress

    stop_request = api.StopEgressRequest(egress_id=egress_id)
    await egress.stop_egress(stop_request)
    logger.info(f"[Egress] Stopped recording {egress_id}")
```

### 4. Integration in medical_agent.py

```python
# After ctx.connect()
egress_id = await start_room_recording(
    room_name=ctx.room.name,
    room_id=ctx.job.id
)

# Store egress_id for later reference
ctx.room.metadata = json.dumps({"egress_id": egress_id})
```

### 5. Webhook Handler (Optional)

Create N8N workflow to receive Egress webhook:

```json
{
  "event": "egress_ended",
  "egress_id": "EG_xxx",
  "room_name": "sbx-xxx",
  "status": "complete",
  "file_results": [{
    "filename": "recordings/AJ_xxx.mp3",
    "size": 1354028,
    "duration": 35.2,
    "download_url": "https://xxx.r2.cloudflarestorage.com/voice-agent-recordings/recordings/AJ_xxx.mp3"
  }]
}
```

## Cost Estimate

**Cloudflare R2:**
- 100 calls/day × 30 days = 3,000 calls/month
- Avg 1 min call = 1MB MP3
- 3,000 MB = 3 GB storage
- **Cost: $0** (within free tier)

**AWS S3:**
- 3 GB storage = $0.069/month
- 3 GB egress = $0.27/month
- **Total: ~$0.34/month**

## Testing

```bash
# Test with a short room
python src/medical_agent.py dev

# Check R2 bucket for recording
# Should see: recordings/<job-id>.mp3
```

## Next Steps

1. Set up Cloudflare R2 bucket
2. Add environment variables
3. Implement start_room_recording()
4. Test with a real call
5. Configure N8N webhook to receive recording URLs
6. Update Airtable with recording URLs
