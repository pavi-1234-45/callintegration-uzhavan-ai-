import asyncio
import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from sqlalchemy import select, update, and_
from app.config import settings
from app.database import AsyncSessionLocal, SyncSessionLocal
from app.models.farmer import Farmer
from app.models.alert import AgriculturalAlert
from app.models.call import CallJob, CallLog
from app.models.scheme import GovernmentScheme
from app.services.tts_service import TTSService
from app.services.telephony import get_telephony_provider
from app.services.weather_service import WeatherService
from app.services.market_service import MarketService
from app.services.scheme_service import SchemeService
from app.services.news_service import NewsService
from app.services.decision_engine import DecisionEngine
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Concurrency semaphore respecting telephony provider rate limits
concurrency_semaphore = asyncio.Semaphore(settings.TELEPHONY_CONCURRENCY_LIMIT)

async def execute_call_job_async(job_id: str) -> bool:
    """
    Executes a single outbound call job asynchronously.
    Synthesizes TTS speech in the farmer's preferred language, logs the call,
    and initiates the outbound call with the telephony provider.
    """
    async with concurrency_semaphore:
        async with AsyncSessionLocal() as db:
            # 1. Fetch Call Job
            stmt = select(CallJob).where(CallJob.job_id == job_id)
            res = await db.execute(stmt)
            job = res.scalars().first()

            if not job or job.status in ("COMPLETED", "CANCELLED"):
                return False

            # Check quiet hours unless emergency override
            if settings.is_in_quiet_hours(job.priority):
                logger.info(f"Call Job {job_id} held: currently in quiet hours ({job.priority})")
                return False

            # 2. Fetch Farmer
            farmer_stmt = select(Farmer).where(Farmer.id == job.farmer_id)
            farmer_res = await db.execute(farmer_stmt)
            farmer = farmer_res.scalars().first()

            if not farmer or not farmer.consent_given or not farmer.voice_alerts_enabled:
                job.status = "CANCELLED"
                await db.commit()
                logger.warning(f"Farmer {job.farmer_id} consent/alerts disabled. Job {job_id} cancelled.")
                return False

            # 3. Fetch Alert data if linked
            alert_data = {}
            alert_type = "WEATHER"
            if job.alert_id:
                alt_stmt = select(AgriculturalAlert).where(AgriculturalAlert.id == job.alert_id)
                alt_res = await db.execute(alt_stmt)
                alert = alt_res.scalars().first()
                if alert:
                    alert_type = alert.alert_type
                    if alert.content_json:
                        try:
                            alert_data = json.loads(alert.content_json)
                        except Exception:
                            pass

            # 4. Render Multilingual Text & Synthesize Speech
            text = TTSService.render_message_text(
                alert_type=alert_type,
                language=job.language,
                farmer_name=farmer.name,
                district=farmer.district,
                crop=farmer.main_crop,
                data=alert_data,
                include_ivr=True
            )

            audio_url = await TTSService.synthesize_speech(text, job.language)
            full_audio_url = f"{settings.BASE_WEBHOOK_URL}{audio_url}" if audio_url else ""

            # 5. Create CallLog entry
            call_id = f"CALL-{uuid.uuid4().hex[:10].upper()}"
            job.attempts += 1
            job.status = "IN_PROGRESS"

            call_log = CallLog(
                call_id=call_id,
                job_id=job.job_id,
                farmer_id=farmer.id,
                alert_id=job.alert_id,
                event_id=job.event_id,
                phone_number=job.phone_number,
                language=job.language,
                call_type=alert_type,
                provider=settings.TELEPHONY_PROVIDER.upper(),
                attempt_number=job.attempts,
                status="CALL_STARTED",
                transcript_text=text,
                audio_url=full_audio_url,
                started_at=datetime.utcnow()
            )
            db.add(call_log)
            await db.commit()

            # 6. Dispatch call via Telephony Provider
            provider = get_telephony_provider()
            call_result = await provider.initiate_call(
                call_id=call_id,
                to_phone=job.phone_number,
                audio_url=full_audio_url,
                text=text,
                language=job.language,
                metadata={"farmer_id": farmer.id, "alert_id": job.alert_id, "attempt": job.attempts}
            )

            if call_result.get("success"):
                call_log.provider_call_id = call_result.get("provider_call_id")
                call_log.status = call_result.get("status", "CALL_STARTED")
                await db.commit()
                return True
            else:
                call_log.status = "FAILED"
                call_log.failure_reason = call_result.get("error", "Call initiation failed")
                await db.commit()
                await handle_call_retry_async(call_id, call_log.failure_reason)
                return False

async def handle_call_retry_async(call_id: str, reason: str):
    """
    Applies configurable retry policy for NO_ANSWER, BUSY, or TEMPORARY_FAILURE.
    """
    async with AsyncSessionLocal() as db:
        stmt = select(CallLog).where(CallLog.call_id == call_id)
        res = await db.execute(stmt)
        call_log = res.scalars().first()
        if not call_log or not call_log.job_id:
            return

        job_stmt = select(CallJob).where(CallJob.job_id == call_log.job_id)
        job_res = await db.execute(job_stmt)
        job = job_res.scalars().first()
        if not job:
            return

        if job.attempts < job.max_retries:
            job.status = "RETRY_PENDING"
            job.next_retry_at = datetime.utcnow() + timedelta(minutes=settings.RETRY_DELAY_MINUTES)
            logger.info(f"Retrying Call Job {job.job_id} (Attempt {job.attempts}/{job.max_retries}) at {job.next_retry_at}")
        else:
            job.status = "FAILED"
            logger.warning(f"Call Job {job.job_id} reached maximum retries ({job.max_retries}). Marked FAILED.")

        await db.commit()

# --- Autonomous Periodic Monitoring Routines ---

async def run_weather_monitoring_cycle():
    """Checks weather for unique registered farmer districts"""
    logger.info("Autonomous Weather Monitor: Checking weather across registered locations.")
    async with AsyncSessionLocal() as db:
        # Get distinct farmer districts and coordinates
        stmt = select(Farmer.district, Farmer.latitude, Farmer.longitude, Farmer.state).where(
            Farmer.voice_alerts_enabled == True,
            Farmer.consent_given == True
        ).distinct()
        res = await db.execute(stmt)
        locations = res.all()

        for district, lat, lon, state in locations:
            try:
                weather_data = await WeatherService.fetch_weather_data(lat, lon, district)
                severity, condition, event_id, desc = WeatherService.evaluate_weather_alert(district, weather_data)

                if severity != "NO_ALERT":
                    # Check if AgriculturalAlert already created
                    alt_stmt = select(AgriculturalAlert).where(AgriculturalAlert.event_id == event_id)
                    alt_res = await db.execute(alt_stmt)
                    existing_alert = alt_res.scalars().first()

                    if not existing_alert:
                        new_alert = AgriculturalAlert(
                            alert_id=f"ALT-WTH-{uuid.uuid4().hex[:8].upper()}",
                            event_id=event_id,
                            alert_type="WEATHER",
                            title=f"{condition.replace('_', ' ').title()} Alert for {district}",
                            severity=severity,
                            state=state,
                            district=district,
                            summary_text=desc,
                            content_json=json.dumps(weather_data)
                        )
                        db.add(new_alert)
                        await db.commit()
                        await db.refresh(new_alert)
                        existing_alert = new_alert

                    # Trigger Decision Engine to match and queue calls
                    await DecisionEngine.process_and_queue_alert(db, existing_alert, weather_data)
            except Exception as e:
                logger.error(f"Weather monitoring failed for {district}: {e}")

async def run_market_monitoring_cycle():
    """Checks daily market prices for registered crops"""
    logger.info("Autonomous Market Monitor: Checking daily mandi prices.")
    async with AsyncSessionLocal() as db:
        crop_stmt = select(Farmer.main_crop).where(
            Farmer.voice_alerts_enabled == True,
            Farmer.consent_given == True
        ).distinct()
        crop_res = await db.execute(crop_stmt)
        crops = [r[0] for r in crop_res.all()]

        for crop in crops:
            try:
                prices = await MarketService.fetch_market_prices(crop=crop)
                if prices:
                    price_item = prices[0]
                    alert_info = MarketService.generate_market_alert(price_item)
                    event_id = alert_info["event_id"]

                    alt_stmt = select(AgriculturalAlert).where(AgriculturalAlert.event_id == event_id)
                    alt_res = await db.execute(alt_stmt)
                    if not alt_res.scalars().first():
                        new_alert = AgriculturalAlert(
                            alert_id=f"ALT-MKT-{uuid.uuid4().hex[:8].upper()}",
                            event_id=event_id,
                            alert_type="MARKET",
                            title=alert_info["title"],
                            severity="NORMAL",
                            crop=crop,
                            summary_text=alert_info["summary"],
                            content_json=json.dumps(alert_info)
                        )
                        db.add(new_alert)
                        await db.commit()
                        await db.refresh(new_alert)
                        await DecisionEngine.process_and_queue_alert(db, new_alert, alert_info)
            except Exception as e:
                logger.error(f"Market monitor failed for crop {crop}: {e}")

# --- Celery Task Wrappers ---

@celery_app.task(name="app.tasks.worker.process_call_job_task")
def process_call_job_task(job_id: str):
    return asyncio.run(execute_call_job_async(job_id))

@celery_app.task(name="app.tasks.worker.autonomous_weather_monitor_task")
def autonomous_weather_monitor_task():
    return asyncio.run(run_weather_monitoring_cycle())

@celery_app.task(name="app.tasks.worker.autonomous_market_monitor_task")
def autonomous_market_monitor_task():
    return asyncio.run(run_market_monitoring_cycle())

@celery_app.task(name="app.tasks.worker.autonomous_scheme_monitor_task")
def autonomous_scheme_monitor_task():
    logger.info("Autonomous Scheme Monitor: Executed")

@celery_app.task(name="app.tasks.worker.autonomous_news_monitor_task")
def autonomous_news_monitor_task():
    logger.info("Autonomous News Monitor: Executed")

@celery_app.task(name="app.tasks.worker.sync_firebase_farmers_task")
def sync_firebase_farmers_task():
    from app.services.firebase_service import FirebaseService
    from app.database import AsyncSessionLocal
    async def _do_sync():
        async with AsyncSessionLocal() as db:
            return await FirebaseService.sync_app_registered_farmers(db)
    return asyncio.run(_do_sync())
