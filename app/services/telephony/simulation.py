import asyncio
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.services.telephony.base import VoiceProvider

logger = logging.getLogger(__name__)

class SimulationTelephonyProvider(VoiceProvider):
    """
    High-Fidelity Telephony Simulation Bridge for testing real call lifecycle,
    DTMF handling, quiet hours, webhook responses, and retry mechanisms.
    """
    def __init__(self):
        self.active_calls = {}

    async def initiate_call(
        self,
        call_id: str,
        to_phone: str,
        audio_url: str,
        text: str,
        language: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        provider_call_id = f"SIM-{uuid.uuid4().hex[:12].upper()}"

        logger.info(f"📞 [Simulation Telephony] Dialing farmer at {to_phone} (Call ID: {call_id})")

        # Determine outcome from phone number or metadata for deterministic testing:
        # e.g., phone ending with 0000 -> BUSY, 1111 -> NO_ANSWER, 9999 -> FAILED, otherwise ANSWERED
        outcome = "ANSWERED"
        if to_phone.endswith("0000"):
            outcome = "BUSY"
        elif to_phone.endswith("1111"):
            outcome = "NO_ANSWER"
        elif to_phone.endswith("9999"):
            outcome = "FAILED"

        self.active_calls[provider_call_id] = {
            "call_id": call_id,
            "to_phone": to_phone,
            "status": "CALL_STARTED",
            "outcome": outcome,
            "started_at": datetime.utcnow()
        }

        # Fire asynchronous background state progression simulating carrier telephony events
        asyncio.create_task(self._simulate_carrier_lifecycle(provider_call_id, call_id, to_phone, outcome, metadata))

        return {
            "success": True,
            "provider": "SIMULATION",
            "provider_call_id": provider_call_id,
            "status": "CALL_STARTED",
            "error": None
        }

    async def _simulate_carrier_lifecycle(
        self,
        provider_call_id: str,
        call_id: str,
        to_phone: str,
        outcome: str,
        metadata: Optional[Dict[str, Any]]
    ):
        """Simulates carrier signaling and posts updates to internal webhook handler"""
        from app.api.webhooks import process_telephony_webhook_event
        from app.schemas.call import WebhookCallEvent

        try:
            # 1. Ringing
            await asyncio.sleep(1.0)
            await process_telephony_webhook_event(
                WebhookCallEvent(
                    call_id=call_id,
                    provider_call_id=provider_call_id,
                    event="RINGING",
                    status="RINGING"
                )
            )

            # 2. Outcome branch
            await asyncio.sleep(1.5)
            if outcome == "BUSY":
                await process_telephony_webhook_event(
                    WebhookCallEvent(
                        call_id=call_id,
                        provider_call_id=provider_call_id,
                        event="BUSY",
                        status="BUSY",
                        failure_reason="Line Busy / User Engaged"
                    )
                )
            elif outcome == "NO_ANSWER":
                await process_telephony_webhook_event(
                    WebhookCallEvent(
                        call_id=call_id,
                        provider_call_id=provider_call_id,
                        event="NO_ANSWER",
                        status="NO_ANSWER",
                        failure_reason="Farmer did not answer after 45 seconds"
                    )
                )
            elif outcome == "FAILED":
                await process_telephony_webhook_event(
                    WebhookCallEvent(
                        call_id=call_id,
                        provider_call_id=provider_call_id,
                        event="FAILED",
                        status="FAILED",
                        failure_reason="Network Congestion / Carrier Temporary Failure"
                    )
                )
            else:
                # Answered & Playing Message
                await process_telephony_webhook_event(
                    WebhookCallEvent(
                        call_id=call_id,
                        provider_call_id=provider_call_id,
                        event="ANSWERED",
                        status="ANSWERED"
                    )
                )

                # Simulate call playback duration
                await asyncio.sleep(2.0)

                # Check if simulated DTMF keypress requested in test metadata
                dtmf_digit = metadata.get("simulate_dtmf") if metadata else None
                if dtmf_digit:
                    await process_telephony_webhook_event(
                        WebhookCallEvent(
                            call_id=call_id,
                            provider_call_id=provider_call_id,
                            event="DTMF",
                            status="ANSWERED",
                            digits=dtmf_digit
                        )
                    )
                    await asyncio.sleep(0.5)

                # Completed
                await process_telephony_webhook_event(
                    WebhookCallEvent(
                        call_id=call_id,
                        provider_call_id=provider_call_id,
                        event="COMPLETED",
                        status="COMPLETED",
                        duration=28, # seconds
                        digits=dtmf_digit
                    )
                )
        except Exception as e:
            logger.error(f"Error during simulated carrier lifecycle: {e}")

    async def get_call_status(self, provider_call_id: str) -> Dict[str, Any]:
        info = self.active_calls.get(provider_call_id, {})
        return {
            "provider_call_id": provider_call_id,
            "status": info.get("status", "UNKNOWN"),
            "duration": 25
        }
