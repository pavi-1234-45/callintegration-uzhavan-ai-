import json
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Depends, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.call import CallLog, CallJob
from app.models.farmer import Farmer
from app.schemas.call import WebhookCallEvent
from app.tasks.worker import handle_call_retry_async

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/voice", tags=["Telephony Webhooks"])

async def process_telephony_webhook_event(event: WebhookCallEvent):
    """
    Core Webhook Processor:
    Updates CallLog, records durations and DTMF keypresses, handles opt-outs,
    and schedules retries on carrier failures.
    """
    async with AsyncSessionLocal() as db:
        # Match by call_id or provider_call_id
        stmt = select(CallLog).where(
            (CallLog.call_id == event.call_id) | (CallLog.provider_call_id == event.provider_call_id)
        )
        res = await db.execute(stmt)
        call_log = res.scalars().first()

        if not call_log:
            logger.warning(f"Webhook received for unknown call: {event.call_id} / {event.provider_call_id}")
            return

        status = event.status or event.event

        # 1. Update Status
        if status in ("CALL_STARTED", "RINGING", "ANSWERED", "BUSY", "NO_ANSWER", "FAILED", "COMPLETED"):
            call_log.status = status

        if event.duration:
            call_log.duration = event.duration

        if event.failure_reason:
            call_log.failure_reason = event.failure_reason

        # 2. Handle DTMF Inputs
        if event.digits:
            call_log.dtmf_response = event.digits
            logger.info(f"DTMF Response received: Key {event.digits} for Call {call_log.call_id}")

            # '0' = Opt out of automated voice alerts
            if event.digits == "0":
                call_log.opted_out = True
                farmer_stmt = select(Farmer).where(Farmer.id == call_log.farmer_id)
                f_res = await db.execute(farmer_stmt)
                farmer = f_res.scalars().first()
                if farmer:
                    farmer.voice_alerts_enabled = False
                    logger.info(f"🚫 Farmer {farmer.name} ({farmer.phone}) successfully OPTED OUT of voice alerts via DTMF.")

        # 3. Handle Completed or Failed state transitions for linked CallJob
        if call_log.job_id:
            job_stmt = select(CallJob).where(CallJob.job_id == call_log.job_id)
            j_res = await db.execute(job_stmt)
            job = j_res.scalars().first()

            if job:
                if status == "COMPLETED":
                    call_log.completed_at = datetime.utcnow()
                    job.status = "COMPLETED"
                elif status in ("BUSY", "NO_ANSWER", "FAILED"):
                    # Retry flow
                    await handle_call_retry_async(call_log.call_id, call_log.failure_reason or status)

        await db.commit()

@router.post("")
async def generic_voice_webhook(event: WebhookCallEvent):
    """Generic JSON Webhook endpoint"""
    await process_telephony_webhook_event(event)
    return {"status": "ok"}

@router.post("/exotel")
async def exotel_webhook(request: Request):
    """
    Exotel Call StatusCallback Handler.
    Parses Exotel URL-encoded form parameters: CallSid, Status, Duration, RecordingUrl, CustomField, etc.
    """
    form_data = await request.form()
    logger.info(f"Exotel Webhook received: {dict(form_data)}")

    provider_call_id = form_data.get("CallSid") or form_data.get("Sid")
    status_raw = form_data.get("Status", "").lower()
    duration = int(form_data.get("Duration", 0) or 0)
    digits = form_data.get("Digits")

    custom_field = form_data.get("CustomField")
    call_id = None
    if custom_field:
        try:
            custom_data = json.loads(custom_field)
            call_id = custom_data.get("call_id")
        except Exception:
            pass

    # Map Exotel status to standard status
    status_map = {
        "in-progress": "ANSWERED",
        "completed": "COMPLETED",
        "busy": "BUSY",
        "no-answer": "NO_ANSWER",
        "failed": "FAILED",
        "canceled": "FAILED"
    }
    status = status_map.get(status_raw, "CALL_STARTED")

    event = WebhookCallEvent(
        call_id=call_id,
        provider_call_id=provider_call_id,
        event=status,
        status=status,
        duration=duration,
        digits=digits
    )
    await process_telephony_webhook_event(event)
    return {"status": "ok"}

@router.post("/twilio")
async def twilio_webhook(request: Request):
    """Twilio StatusCallback Webhook handler"""
    form_data = await request.form()
    logger.info(f"Twilio Webhook: {dict(form_data)}")

    provider_call_id = form_data.get("CallSid")
    call_status = form_data.get("CallStatus", "").lower()
    duration = int(form_data.get("CallDuration", 0) or 0)
    digits = form_data.get("Digits")

    status_map = {
        "ringing": "RINGING",
        "in-progress": "ANSWERED",
        "completed": "COMPLETED",
        "busy": "BUSY",
        "no-answer": "NO_ANSWER",
        "failed": "FAILED"
    }
    status = status_map.get(call_status, "CALL_STARTED")

    event = WebhookCallEvent(
        provider_call_id=provider_call_id,
        event=status,
        status=status,
        duration=duration,
        digits=digits
    )
    await process_telephony_webhook_event(event)
    return {"status": "ok"}

@router.get("/twiml")
async def twiml_response(call_id: Optional[str] = None):
    """
    Renders TwiML XML for Twilio calls with <Play> or <Say> and <Gather> for DTMF menu
    """
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Response>\n'
        '  <Gather numDigits="1" timeout="10">\n'
        '    <Say language="ta-IN">வணக்கம். உழவன் AI அவசர அறிவிப்பு.</Say>\n'
        '  </Gather>\n'
        '</Response>'
    )
    return Response(content=twiml, media_type="application/xml")
