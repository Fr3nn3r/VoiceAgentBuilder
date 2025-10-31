"""
HTTP client for scheduling webhook endpoints.

Handles all HTTP communication with N8N scheduling webhooks.
Follows Single Responsibility Principle: only manages HTTP requests.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger("scheduling.webhook_client")


class SchedulingToolHandler:
    """Handles webhook calls for scheduling tools"""

    def __init__(self, base_url: str, api_token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def _call_webhook(
        self, endpoint: str, payload: Dict[str, Any], timeout: float = 8.0
    ) -> Dict[str, Any]:
        """Make HTTP POST request to webhook endpoint"""
        await self._ensure_session()

        url = f"{self.base_url}/{endpoint}"
        headers = {"Content-Type": "application/json"}

        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        logger.info(f"[Webhook] Calling {url} with payload: {payload}")

        try:
            async with self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"[Webhook] Success: {data}")
                    return data
                else:
                    error_text = await response.text()
                    logger.error(f"[Webhook] Error {response.status}: {error_text}")
                    return {"error": f"HTTP {response.status}", "detail": error_text}
        except asyncio.TimeoutError:
            logger.error(f"[Webhook] Timeout after {timeout}s")
            return {"error": "timeout", "detail": "Request timed out"}
        except Exception as e:
            logger.error(f"[Webhook] Exception: {type(e).__name__}: {e}")
            return {"error": str(type(e).__name__), "detail": str(e)}

    async def check_availability(
        self, start_datetime: str, end_datetime: str
    ) -> Dict[str, Any]:
        """Check if appointment slot is available"""
        payload = {
            "action": "check_availability",
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
        }
        result = await self._call_webhook("check_availability", payload)
        return result

    async def book_appointment(
        self, start_datetime: str, end_datetime: str, summary: str
    ) -> Dict[str, Any]:
        """Book an appointment"""
        payload = {
            "action": "book_appointment",
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "summary": summary,
        }
        result = await self._call_webhook("book_appointment", payload)
        return result

    async def log_appointment_details(
        self,
        event: str,
        date: str,
        start_time: str,
        end_time: str,
        patient_name: str,
        birth_date: Optional[str],
        phone_number: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Log appointment details to backend"""
        payload = {
            "action": "log_appointment",
            "event": event,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "patient_name": patient_name,
            "birth_date": birth_date,
            "phone_number": phone_number,
            "reason": reason,
        }
        result = await self._call_webhook("log_appointment", payload)
        return result

    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
