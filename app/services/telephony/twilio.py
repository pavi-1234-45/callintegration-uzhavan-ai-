import httpx
import logging
from typing import Dict, Any, Optional
from app.config import settings
from app.services.telephony.base import VoiceProvider

logger = logging.getLogger(__name__)

class TwilioVoiceProvider(VoiceProvider):
    """
    Twilio Telephony Provider for Outbound Calls and TwiML integration.
    """
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_phone = settings.TWILIO_PHONE_NUMBER

    async def initiate_call(
        self,
        call_id: str,
        to_phone: str,
        audio_url: str,
        text: str,
        language: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not (self.account_sid and self.auth_token and self.from_phone):
            return {
                "success": False,
                "provider": "TWILIO",
                "provider_call_id": None,
                "status": "FAILED",
                "error": "Twilio credentials not configured in .env"
            }

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls.json"
        webhook_url = f"{settings.BASE_WEBHOOK_URL}/webhooks/voice/twilio?call_id={call_id}"
        twiml_url = f"{settings.BASE_WEBHOOK_URL}/webhooks/voice/twiml?call_id={call_id}"

        payload = {
            "To": to_phone,
            "From": self.from_phone,
            "Url": twiml_url,
            "StatusCallback": webhook_url,
            "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"],
            "StatusCallbackMethod": "POST"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    url,
                    data=payload,
                    auth=(self.account_sid, self.auth_token)
                )
                if res.status_code in (200, 201):
                    data = res.json()
                    return {
                        "success": True,
                        "provider": "TWILIO",
                        "provider_call_id": data.get("sid"),
                        "status": "CALL_STARTED",
                        "error": None
                    }
                else:
                    return {
                        "success": False,
                        "provider": "TWILIO",
                        "provider_call_id": None,
                        "status": "FAILED",
                        "error": f"Twilio API error {res.status_code}: {res.text}"
                    }
        except Exception as e:
            logger.error(f"Twilio exception: {e}")
            return {
                "success": False,
                "provider": "TWILIO",
                "provider_call_id": None,
                "status": "FAILED",
                "error": str(e)
            }

    async def get_call_status(self, provider_call_id: str) -> Dict[str, Any]:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls/{provider_call_id}.json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, auth=(self.account_sid, self.auth_token))
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "provider_call_id": provider_call_id,
                        "status": data.get("status"),
                        "duration": data.get("duration", 0)
                    }
        except Exception as e:
            logger.error(f"Twilio status query error: {e}")
        return {"provider_call_id": provider_call_id, "status": "UNKNOWN"}
