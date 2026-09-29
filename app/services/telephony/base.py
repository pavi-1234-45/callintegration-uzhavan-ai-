from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class VoiceProvider(ABC):
    @abstractmethod
    async def initiate_call(
        self,
        call_id: str,
        to_phone: str,
        audio_url: str,
        text: str,
        language: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Initiates an outbound phone call to the farmer's registered phone number.
        Returns a dict:
        {
            "success": bool,
            "provider": str,
            "provider_call_id": str,
            "status": str, # e.g. CALL_STARTED, QUEUED
            "error": Optional[str]
        }
        """
        pass

    @abstractmethod
    async def get_call_status(self, provider_call_id: str) -> Dict[str, Any]:
        """
        Queries call status from the telephony provider.
        """
        pass
