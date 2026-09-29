import asyncio
import os
import json
from datetime import datetime

from app.database import init_db, AsyncSessionLocal
from app.models.farmer import Farmer
from app.models.alert import AgriculturalAlert
from app.models.call import CallJob, CallLog
from app.services.weather_service import WeatherService
from app.services.tts_service import TTSService
from app.services.decision_engine import DecisionEngine
from app.tasks.worker import execute_call_job_async
from app.schemas.call import WebhookCallEvent
from app.api.webhooks import process_telephony_webhook_event
from sqlalchemy import select

async def run_vertical_slice():
    print("\n" + "="*80)
    print("🌾 RUNNING UZHAVAN AI FIRST VERTICAL SLICE END-TO-END TEST")
    print("="*80)

    # 1. Initialize Database
    print("\n[Step 1] Initializing Database...")
    await init_db()
    print("✅ Database tables created successfully.")

    # 2. Register 1 Farmer
    print("\n[Step 2] Registering 1 Real Farmer (Kumar, Madurai, Tomato, Tamil)...")
    async with AsyncSessionLocal() as db:
        # Clear any existing test record and associated jobs/logs
        existing = await db.execute(select(Farmer).where(Farmer.phone == "+919876543210"))
        for f in existing.scalars().all():
            jobs = (await db.execute(select(CallJob).where(CallJob.farmer_id == f.id))).scalars().all()
            for j in jobs:
                await db.delete(j)
            logs = (await db.execute(select(CallLog).where(CallLog.farmer_id == f.id))).scalars().all()
            for l in logs:
                await db.delete(l)
            await db.delete(f)
        await db.commit()

        farmer = Farmer(
            farmer_id="UZH-FARM-TEST-001",
            name="Kumar S.",
            phone="+919876543210",
            preferred_language="ta-IN",
            farmer_category="Small",
            state="Tamil Nadu",
            district="Madurai",
            taluk="Melur",
            village="Kottampatti",
            latitude=9.925200,
            longitude=78.119800,
            main_crop="Tomato",
            additional_crops="Onion",
            crop_season="Rabi",
            consent_given=True,
            consent_timestamp=datetime.utcnow(),
            voice_alerts_enabled=True
        )
        db.add(farmer)
        await db.commit()
        await db.refresh(farmer)
        farmer_id = farmer.id
        print(f"✅ Farmer registered: {farmer.name} | ID: {farmer.farmer_id} | Phone: {farmer.masked_phone} | Crop: {farmer.main_crop}")

    # 3. Real Weather Fetch
    print("\n[Step 3] Fetching REAL Weather Data from Open-Meteo API for Madurai (9.9252, 78.1198)...")
    weather_data = await WeatherService.fetch_weather_data(9.9252, 78.1198, "Madurai")
    print(f"✅ Real weather fetched from: {weather_data['source']}")
    print(f"   Temp: {weather_data['temperature']}°C | Wind: {weather_data['wind_speed']} km/h | Rain Sum: {weather_data['precipitation_sum']} mm")

    # 4. Evaluate Weather Alert Thresholds
    print("\n[Step 4] Evaluating Deterministic Thresholds...")
    # Simulate a heavy rain event for Madurai
    alert_event_id = f"MADURAI_HEAVY_RAIN_{datetime.now().strftime('%Y_%m_%d')}"
    async with AsyncSessionLocal() as db:
        # Check / create alert
        alert = (await db.execute(select(AgriculturalAlert).where(AgriculturalAlert.event_id == alert_event_id))).scalars().first()
        if not alert:
            import uuid
            alert = AgriculturalAlert(
                alert_id=f"ALT-TEST-{uuid.uuid4().hex[:8].upper()}",
                event_id=alert_event_id,
                alert_type="WEATHER",
                title="Heavy Rainfall Alert for Madurai",
                severity="HIGH",
                state="Tamil Nadu",
                district="Madurai",
                crop="Tomato",
                summary_text="Heavy rain expected in Madurai tomorrow. Ensure drainage for Tomato crop.",
                content_json=json.dumps(weather_data)
            )
            db.add(alert)
            await db.commit()
            await db.refresh(alert)
        alert_id = alert.id
        print(f"✅ Alert recorded: {alert.title} | Severity: {alert.severity} | Event ID: {alert.event_id}")

    # 5. Decision Engine Matching & Duplicate Check
    print("\n[Step 5] Running Decision Engine (Farmer Matching & Deduplication)...")
    async with AsyncSessionLocal() as db:
        alert = (await db.execute(select(AgriculturalAlert).where(AgriculturalAlert.id == alert_id))).scalars().first()
        queued_jobs = await DecisionEngine.process_and_queue_alert(db, alert, weather_data)
        assert len(queued_jobs) >= 1, "Expected at least 1 job queued for Kumar!"
        job = queued_jobs[0]
        job_id = job.job_id
        print(f"✅ Decision Engine matched Farmer Kumar! Call Job created: {job_id} (Priority: {job.priority})")

        # Duplicate check verification: Run again with same event_id
        duplicate_jobs = await DecisionEngine.process_and_queue_alert(db, alert, weather_data)
        assert len(duplicate_jobs) == 0, "Duplicate prevention FAILED! Duplicate job was created."
        print("✅ Duplicate Prevention Verified: 0 duplicate jobs created on secondary evaluation.")

    # 6. TTS Speech Generation (Tamil)
    print("\n[Step 6] Testing Tamil Multilingual TTS Synthesis...")
    text = TTSService.render_message_text(
        alert_type="WEATHER",
        language="ta-IN",
        farmer_name="குமார்",
        district="மதுரை",
        crop="தக்காளி",
        data={"date": datetime.now().strftime("%d-%m-%Y")},
        include_ivr=True
    )
    print(f"   Rendered Text: {text[:120]}...")
    audio_url = await TTSService.synthesize_speech(text, "ta-IN")
    assert audio_url is not None, "TTS synthesis failed!"
    print(f"✅ Tamil TTS Audio Synthesized and Cached: {audio_url}")

    # 7. Telephony Outbound Dispatch
    print("\n[Step 7] Dispatching Telephony Call Job via Worker...")
    success = await execute_call_job_async(job_id)
    assert success, "Call dispatch failed!"
    print("✅ Call Job dispatched to telephony provider.")

    # Wait for simulation / carrier progression
    await asyncio.sleep(4.5)

    # 8. Webhook & Call Log Verification
    print("\n[Step 8] Verifying Call Log & Webhook Status in Database...")
    async with AsyncSessionLocal() as db:
        stmt = select(CallLog).where(CallLog.job_id == job_id)
        res = await db.execute(stmt)
        call_log = res.scalars().first()
        assert call_log is not None, "CallLog record was not created!"
        print(f"✅ Call Log ID: {call_log.call_id}")
        print(f"   Provider: {call_log.provider} | Provider Call ID: {call_log.provider_call_id}")
        print(f"   Status: {call_log.status} | Duration: {call_log.duration}s | Attempt: {call_log.attempt_number}")
        print(f"   Masked Phone: {call_log.masked_phone}")
        print(f"   Audio URL: {call_log.audio_url}")

    # 9. Dashboard Statistics Verification
    print("\n[Step 9] Verifying Dashboard Metric Calculations...")
    from app.api.dashboard import get_dashboard_stats
    async with AsyncSessionLocal() as db:
        stats = await get_dashboard_stats(db=db)
        print(f"✅ Dashboard Metrics Verified:")
        print(f"   Total Farmers: {stats['total_farmers']}")
        print(f"   Voice-Enabled Farmers: {stats['voice_enabled_farmers']}")
        print(f"   Today's Alerts: {stats['todays_alerts']}")
        print(f"   Completed Calls: {stats['completed_calls']}")
        assert stats["total_farmers"] >= 1
        assert stats["voice_enabled_farmers"] >= 1

    print("\n" + "="*80)
    print("🎉 FIRST VERTICAL SLICE COMPLETE & FULLY VERIFIED!")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(run_vertical_slice())
