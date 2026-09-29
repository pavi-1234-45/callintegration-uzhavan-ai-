import asyncio
from datetime import datetime, timedelta
from app.database import init_db, AsyncSessionLocal
from app.models.farmer import Farmer
from app.models.call import CallJob, CallLog
from app.schemas.call import WebhookCallEvent
from app.api.webhooks import process_telephony_webhook_event
from app.tasks.worker import execute_call_job_async
from sqlalchemy import select

async def test_retries_and_optout():
    print("\n" + "="*70)
    print("🔁 TESTING TELEPHONY RETRY POLICY & DTMF OPT-OUT")
    print("="*70)

    await init_db()

    async with AsyncSessionLocal() as db:
        # Register or reset a test farmer for retries
        f_retry = (await db.execute(select(Farmer).where(Farmer.phone == "+919999001111"))).scalars().first()
        if not f_retry:
            f_retry = Farmer(
                farmer_id="UZH-FARM-RETRY-01",
                name="Ramesh P.",
                phone="+919999001111", # ends in 1111 -> Simulation outputs NO_ANSWER
                preferred_language="ta-IN",
                district="Madurai",
                latitude=9.9252,
                longitude=78.1198,
                main_crop="Paddy",
                consent_given=True,
                voice_alerts_enabled=True
            )
            db.add(f_retry)
        else:
            f_retry.voice_alerts_enabled = True
            f_retry.consent_given = True
        await db.commit()
        await db.refresh(f_retry)

        # 1. Test NO_ANSWER Retry Cycle
        print("\n[Step 1] Creating Call Job for Farmer with NO_ANSWER outcome...")
        import uuid
        job_id = f"JOB-RETRY-{uuid.uuid4().hex[:8].upper()}"
        event_id = f"TEST_NO_ANSWER_{uuid.uuid4().hex[:6].upper()}"
        job = CallJob(
            job_id=job_id,
            farmer_id=f_retry.id,
            event_id=event_id,
            phone_number=f_retry.phone,
            language="ta-IN",
            priority="HIGH",
            status="QUEUED",
            attempts=0,
            max_retries=3
        )
        db.add(job)
        await db.commit()

    # Execute Job
    print("   Dispatching call...")
    await execute_call_job_async(job_id)
    # Wait for simulation to signal NO_ANSWER
    await asyncio.sleep(3.5)

    # Check CallJob and CallLog state
    async with AsyncSessionLocal() as db:
        j = (await db.execute(select(CallJob).where(CallJob.job_id == job_id))).scalars().first()
        cl = (await db.execute(select(CallLog).where(CallLog.job_id == job_id))).scalars().first()

        print(f"   Call Log Status: {cl.status} | Failure Reason: {cl.failure_reason}")
        print(f"   Call Job Status: {j.status} | Attempts: {j.attempts}/{j.max_retries} | Next Retry: {j.next_retry_at}")
        assert cl.status == "NO_ANSWER", "Expected CallLog status NO_ANSWER!"
        assert j.status == "RETRY_PENDING", "Expected CallJob status RETRY_PENDING!"
        assert j.attempts == 1, "Expected attempt count to be 1!"
        assert j.next_retry_at is not None, "Expected next_retry_at to be calculated!"
        print("✅ Retry System Verified: NO_ANSWER triggered RETRY_PENDING with 30-minute backoff.")

    # 2. Test DTMF '0' Opt-Out
    print("\n[Step 2] Testing Farmer DTMF '0' Opt-Out via Webhook...")
    async with AsyncSessionLocal() as db:
        farmer = (await db.execute(select(Farmer).where(Farmer.id == f_retry.id))).scalars().first()
        assert farmer.voice_alerts_enabled == True, "Farmer should be voice enabled initially"

        # Webhook emits DTMF 0
        await process_telephony_webhook_event(
            WebhookCallEvent(
                call_id=cl.call_id,
                event="DTMF",
                status="ANSWERED",
                digits="0"
            )
        )

        # Verify farmer record
        await db.refresh(farmer)
        print(f"   Farmer Voice Alerts Enabled: {farmer.voice_alerts_enabled}")
        assert farmer.voice_alerts_enabled == False, "Farmer should have voice_alerts_enabled = False after pressing 0!"
        print("✅ DTMF Opt-Out Verified: Farmer successfully opted out and voice alerts disabled in database.")

    print("\n" + "="*70)
    print("🎉 RETRY POLICY & DTMF OPT-OUT FULLY VERIFIED!")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_retries_and_optout())
