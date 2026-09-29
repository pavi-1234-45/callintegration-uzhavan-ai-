import httpx
import json
import logging
from typing import Dict, Any, Optional
from app.config import settings
from app.services.telephony.base import VoiceProvider

logger = logging.getLogger(__name__)

class ExotelVoiceProvider(VoiceProvider):
    """
    Production Telephony Provider for Exotel Voice API (India).
    Connects calls to Indian farmers via PSTN carrier network.
    """
    def __init__(self):
        self.account_sid = settings.EXOTEL_ACCOUNT_SID
        self.api_key = settings.EXOTEL_API_KEY
        self.api_token = settings.EXOTEL_API_TOKEN
        self.caller_id = settings.EXOTEL_CALLER_ID
        self.subdomain = settings.EXOTEL_SUBDOMAIN or "api.exotel.com"

    async def initiate_call(
        self,
        call_id: str,
        to_phone: str,
        audio_url: str,
        text: str,
        language: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not (self.account_sid and self.api_key and self.api_token):
            return {
                "success": False,
                "provider": "EXOTEL",
                "provider_call_id": None,
                "status": "FAILED",
                "error": "Exotel credentials not configured in .env"
            }

        url = f"https://{self.api_key}:{self.api_token}@{self.subdomain}/v1/Accounts/{self.account_sid}/Calls/connect.json"
        
        # Build webhook status callback URL
        webhook_url = f"{settings.BASE_WEBHOOK_URL}/webhooks/voice/exotel"

        # Exotel expects standard 10 digit Indian number without '+' or leading 0
        cleaned_to = to_phone.replace("+91", "").replace("+", "").strip()

        payload = {
            "From": cleaned_to,
            "To": cleaned_to,
            "CallerId": self.caller_id,
            "CallType": "trans",
            "StatusCallback": webhook_url,
            "CustomField": json.dumps({
                "call_id": call_id,
                "language": language,
                **(metadata or {})
            })
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, data=payload)
                if res.status_code in (200, 201):
                    data = res.json()
                    call_data = data.get("Call", {})
                    provider_call_id = call_data.get("Sid")
                    return {
                        "success": True,
                        "provider": "EXOTEL",
                        "provider_call_id": provider_call_id,
                        "status": "CALL_STARTED",
                        "error": None
                    }
                else:
                    logger.error(f"Exotel call failed ({res.status_code}): {res.text}")
                    return {
                        "success": False,
                        "provider": "EXOTEL",
                        "provider_call_id": None,
                        "status": "FAILED",
                        "error": f"Exotel API returned HTTP {res.status_code}: {res.text}"
                    }
        except Exception as e:
            logger.error(f"Exotel exception: {e}")
            return {
                "success": False,
                "provider": "EXOTEL",
                "provider_call_id": None,
                "status": "FAILED",
                "error": str(e)
            }

    async def get_call_status(self, provider_call_id: str) -> Dict[str, Any]:
        url = f"https://{self.api_key}:{self.api_token}@{self.subdomain}/v1/Accounts/{self.account_sid}/Calls/{provider_call_id}.json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    call_info = data.get("Call", {})
                    return {
                        "provider_call_id": provider_call_id,
                        "status": call_info.get("Status"),
                        "duration": call_info.get("Duration", 0)
                    }
        except Exception as e:
            logger.error(f"Exotel status fetch error: {e}")
        return {"provider_call_id": provider_call_id, "status": "UNKNOWN"}
