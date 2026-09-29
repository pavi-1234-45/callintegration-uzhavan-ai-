from app.config import settings
from app.services.telephony.base import VoiceProvider
from app.services.telephony.exotel import ExotelVoiceProvider
from app.services.telephony.twilio import TwilioVoiceProvider
from app.services.telephony.simulation import SimulationTelephonyProvider

def get_telephony_provider() -> VoiceProvider:
    provider_name = settings.TELEPHONY_PROVIDER.lower()
    if provider_name == "exotel":
        return ExotelVoiceProvider()
    elif provider_name == "twilio":
        return TwilioVoiceProvider()
    else:
        return SimulationTelephonyProvider()

__all__ = ["VoiceProvider", "ExotelVoiceProvider", "TwilioVoiceProvider", "SimulationTelephonyProvider", "get_telephony_provider"]
