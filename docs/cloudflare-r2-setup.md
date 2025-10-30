# Cloudflare R2 Setup for LiveKit Egress Recording

## Why Cloudflare R2?

- **Free tier**: 10 GB storage, 1M Class A operations/month
- **No egress fees**: Unlike AWS S3, R2 doesn't charge for data transfer
- **S3-compatible**: Works with LiveKit's S3 integration
- **Fast**: Global CDN for fast audio delivery

## Setup Steps (15 minutes)

### 1. Create Cloudflare Account

1. Go to [cloudflare.com](https://cloudflare.com)
2. Sign up for free account
3. Verify email

### 2. Enable R2

1. In Cloudflare dashboard, click **R2** in left sidebar
2. Click **Purchase R2 plan** (don't worry, free tier is generous)
3. Add payment method (required but won't be charged under free tier limits)

### 3. Create R2 Bucket

1. Click **Create bucket**
2. **Bucket name**: `voice-agent-recordings`
3. **Location**: Auto (Cloudflare chooses optimal location)
4. Click **Create bucket**

### 4. Create API Token

1. Go to **R2** → **Manage R2 API Tokens**
2. Click **Create API token**
3. **Token name**: `livekit-egress`
4. **Permissions**: Select **Object Read & Write**
5. **TTL**: Never expire (or set expiry if you prefer)
6. Click **Create API Token**

7. **Save these values** (you won't see them again):
   ```
   Access Key ID: 1234567890abcdef1234567890abcdef
   Secret Access Key: abcdef1234567890abcdef1234567890abcdef12
   ```

### 5. Get R2 Endpoint

Your R2 endpoint follows this format:
```
https://<account-id>.r2.cloudflarestorage.com
```

To find your account ID:
1. Go to **R2** → **Overview**
2. Look for **Jurisdiction-specific Endpoints for S3 Clients**
3. Copy the endpoint URL (e.g., `https://abc123def456.r2.cloudflarestorage.com`)

### 6. Configure Environment Variables

Add these to your `.env` file:

```bash
# LiveKit Egress Recording
S3_ACCESS_KEY=1234567890abcdef1234567890abcdef
S3_SECRET_KEY=abcdef1234567890abcdef1234567890abcdef12
S3_ENDPOINT=https://abc123def456.r2.cloudflarestorage.com
S3_BUCKET=voice-agent-recordings
S3_REGION=auto
```

### 7. Test the Setup

Run your voice agent:
```bash
uv run python src/medical_agent.py dev
```

Look for these logs:
```
[Config] Egress recording enabled
[Egress] Started recording EG_xxx for room sbx-xxx
[Egress] Recording will be saved to recordings/AJ_xxx.mp3
```

After the call ends, check your R2 bucket:
1. Go to **R2** → **voice-agent-recordings**
2. Navigate to **recordings** folder
3. You should see `<job-id>.mp3`

### 8. Make Recordings Public (Optional)

By default, R2 objects are private. To make recordings publicly accessible:

**Option A: Public Bucket (Simple)**
1. Go to R2 bucket → **Settings**
2. Under **Public access**, click **Allow Access**
3. Configure allowed domains or leave open
4. Recordings will be accessible at: `https://pub-xxx.r2.dev/recordings/<job-id>.mp3`

**Option B: Custom Domain (Recommended for production)**
1. Go to R2 bucket → **Settings** → **Custom Domains**
2. Click **Connect Domain**
3. Enter your domain (e.g., `recordings.yourdomain.com`)
4. Follow DNS setup instructions
5. Recordings will be accessible at: `https://recordings.yourdomain.com/recordings/<job-id>.mp3`

**Option C: Signed URLs (Most secure)**
- Generate temporary signed URLs for each recording
- URLs expire after specified time
- Implement in N8N or backend

## Cost Estimate

**Free Tier Limits:**
- 10 GB storage/month
- 1 million Class A operations/month (list, write)
- 10 million Class B operations/month (read)
- Unlimited egress (FREE!)

**Your Usage (estimated):**
- 100 calls/day × 30 days = 3,000 calls/month
- Average 1-minute call = ~1 MB MP3
- **Storage**: 3 GB/month → **FREE** ✅
- **Write operations**: 3,000/month → **FREE** ✅
- **Read operations** (playback): 3,000/month → **FREE** ✅

**You'll stay within free tier indefinitely!**

## Troubleshooting

### "Egress recording disabled"
**Problem**: Missing S3 credentials in environment

**Solution**: Check `.env` file has all S3_ variables set

### "Failed to start recording"
**Problem**: Invalid credentials or bucket name

**Solution**:
1. Verify Access Key ID and Secret Access Key are correct
2. Verify bucket name is `voice-agent-recordings` (exact match)
3. Check endpoint URL format

### "No recording in bucket after call"
**Problem**: Egress failed or recording still processing

**Solution**:
1. Wait 30-60 seconds after call ends (Egress needs time to upload)
2. Check LiveKit dashboard → **Egress** tab for errors
3. Verify room actually had audio (test with a real call, not just connection)

### "Access Denied" when accessing recording
**Problem**: Bucket is private and recording URL is not public

**Solution**: Enable public access (see step 8 above) or use signed URLs

## Next Steps

1. ✅ Set up R2 bucket
2. ✅ Configure environment variables
3. ✅ Test with a real call
4. Configure N8N to receive recording URLs
5. Update Airtable with recording links
6. (Optional) Set up custom domain for recordings
