"""
LiveKit Egress recording for room audio.
Server-side recording that captures mixed audio (user + agent).
"""

import logging
import os
from typing import Optional

from livekit import api

logger = logging.getLogger("egress_recording")


class EgressRecorder:
    """
    Manages LiveKit Egress room composite recordings.

    Records mixed room audio server-side and uploads to S3-compatible storage.
    """

    def __init__(
        self,
        livekit_url: str,
        api_key: str,
        api_secret: str,
        s3_access_key: str,
        s3_secret_key: str,
        s3_endpoint: str,
        s3_bucket: str,
        s3_region: str = "auto",
    ):
        """
        Initialize Egress recorder with LiveKit and S3 credentials.

        Args:
            livekit_url: LiveKit server URL (e.g., wss://your-project.livekit.cloud)
            api_key: LiveKit API key
            api_secret: LiveKit API secret
            s3_access_key: S3/R2 access key
            s3_secret_key: S3/R2 secret key
            s3_endpoint: S3/R2 endpoint URL
            s3_bucket: S3/R2 bucket name
            s3_region: S3/R2 region (default: auto for Cloudflare R2)
        """
        self.livekit_url = livekit_url
        self.api_key = api_key
        self.api_secret = api_secret

        self.s3_access_key = s3_access_key
        self.s3_secret_key = s3_secret_key
        self.s3_endpoint = s3_endpoint
        self.s3_bucket = s3_bucket
        self.s3_region = s3_region

        # Initialize LiveKit API client (SDK v1.0+)
        self.lkapi = api.LiveKitAPI(livekit_url, api_key, api_secret)
        self.egress_service = self.lkapi.egress

        logger.info(
            f"[Egress] Initialized (bucket={s3_bucket}, endpoint={s3_endpoint})"
        )

    async def start_room_recording(
        self, room_name: str, room_id: str
    ) -> Optional[str]:
        """
        Start room composite audio recording.

        Args:
            room_name: LiveKit room name
            room_id: Unique identifier for this recording (usually job ID)

        Returns:
            Egress ID if successful, None otherwise
        """
        try:
            # Configure S3 upload (force path-style for Azure Blob Storage compatibility)
            s3_upload = api.S3Upload(
                access_key=self.s3_access_key,
                secret=self.s3_secret_key,
                region=self.s3_region,
                endpoint=self.s3_endpoint,
                bucket=self.s3_bucket,
                force_path_style=True,  # Required for Azure Blob Storage
            )

            # Configure audio-only MP4 recording (MP3 not supported in SDK v1.0+)
            request = api.RoomCompositeEgressRequest(
                room_name=room_name,
                audio_only=True,  # Audio only, no video
                file_outputs=[
                    api.EncodedFileOutput(
                        file_type=api.EncodedFileType.MP4,
                        filepath=f"recordings/{room_id}.mp4",
                        s3=s3_upload,
                    )
                ],
            )

            # Start recording
            egress = await self.egress_service.start_room_composite_egress(request)

            logger.info(
                f"[Egress] Started recording {egress.egress_id} for room {room_name}"
            )
            logger.info(f"[Egress] Recording will be saved to recordings/{room_id}.mp4")

            return egress.egress_id

        except Exception as e:
            logger.error(f"[Egress] Failed to start recording: {e}")
            return None

    async def stop_recording(self, egress_id: str) -> bool:
        """
        Stop an active recording (optional - recordings auto-stop when room ends).

        Args:
            egress_id: Egress ID from start_room_recording()

        Returns:
            True if successful, False otherwise
        """
        try:
            stop_request = api.StopEgressRequest(egress_id=egress_id)
            await self.egress_service.stop_egress(stop_request)
            logger.info(f"[Egress] Stopped recording {egress_id}")
            return True

        except Exception as e:
            logger.error(f"[Egress] Failed to stop recording: {e}")
            return False

    async def get_recording_info(self, egress_id: str) -> Optional[dict]:
        """
        Get information about a recording.

        Args:
            egress_id: Egress ID from start_room_recording()

        Returns:
            Dict with recording info, or None if not found
        """
        try:
            list_request = api.ListEgressRequest(egress_id=egress_id)
            response = await self.egress_service.list_egress(list_request)

            if not response or not response.items:
                return None

            egress = response.items[0]

            return {
                "egress_id": egress.egress_id,
                "status": egress.status,
                "room_name": egress.room_name,
                "started_at": egress.started_at,
                "ended_at": egress.ended_at if hasattr(egress, "ended_at") else None,
            }

        except Exception as e:
            logger.error(f"[Egress] Failed to get recording info: {e}")
            return None

    async def close(self):
        """
        Close the LiveKit API client and cleanup resources.
        """
        try:
            await self.lkapi.aclose()
            logger.info("[Egress] Closed LiveKit API client")
        except Exception as e:
            logger.error(f"[Egress] Error closing API client: {e}")


def create_egress_recorder_from_env() -> Optional[EgressRecorder]:
    """
    Create EgressRecorder from environment variables.

    Required env vars:
    - LIVEKIT_URL
    - LIVEKIT_API_KEY
    - LIVEKIT_API_SECRET
    - S3_ACCESS_KEY (or R2_ACCESS_KEY)
    - S3_SECRET_KEY (or R2_SECRET_KEY)
    - S3_ENDPOINT (or R2_ENDPOINT)
    - S3_BUCKET (or R2_BUCKET)
    - S3_REGION (optional, default: auto)

    Returns:
        EgressRecorder instance, or None if env vars missing
    """
    livekit_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    # Support both S3_ and R2_ prefixes
    s3_access_key = os.getenv("S3_ACCESS_KEY") or os.getenv("R2_ACCESS_KEY")
    s3_secret_key = os.getenv("S3_SECRET_KEY") or os.getenv("R2_SECRET_KEY")
    s3_endpoint = os.getenv("S3_ENDPOINT") or os.getenv("R2_ENDPOINT")
    s3_bucket = os.getenv("S3_BUCKET") or os.getenv("R2_BUCKET")
    s3_region = os.getenv("S3_REGION", "auto")

    # Check required vars
    missing = []
    if not livekit_url:
        missing.append("LIVEKIT_URL")
    if not api_key:
        missing.append("LIVEKIT_API_KEY")
    if not api_secret:
        missing.append("LIVEKIT_API_SECRET")
    if not s3_access_key:
        missing.append("S3_ACCESS_KEY or R2_ACCESS_KEY")
    if not s3_secret_key:
        missing.append("S3_SECRET_KEY or R2_SECRET_KEY")
    if not s3_endpoint:
        missing.append("S3_ENDPOINT or R2_ENDPOINT")
    if not s3_bucket:
        missing.append("S3_BUCKET or R2_BUCKET")

    if missing:
        logger.warning(
            f"[Egress] Cannot create recorder - missing env vars: {', '.join(missing)}"
        )
        logger.warning("[Egress] Room recordings will NOT be enabled")
        return None

    return EgressRecorder(
        livekit_url=livekit_url,
        api_key=api_key,
        api_secret=api_secret,
        s3_access_key=s3_access_key,
        s3_secret_key=s3_secret_key,
        s3_endpoint=s3_endpoint,
        s3_bucket=s3_bucket,
        s3_region=s3_region,
    )
