import pytest
import pytest_asyncio
import uuid
import random
import json
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.database import AsyncSessionLocal
from app.models.farmer import Farmer
from app.models.alert import AgriculturalAlert
from app.models.call import CallJob, CallLog
from app.services.firebase_service import FirebaseService
from app.services.decision_engine import DecisionEngine
from app.tasks.worker import execute_call_job_async

@pytest.mark.asyncio
async def test_firebase_backend_status():
    """Validates Firebase connection status endpoint reflects uzhavan-ai-686d6 backend"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/firebase/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["project_id"] == "uzhavan-ai-686d6"
        assert "Cloud Firestore" in data["database"]

@pytest.mark.asyncio
async def test_firebase_data_sync_and_population():
    """
    Tests syncing app-registered farmers into the portal database:
    - Verifies fields (name, phone, district, main_crop, language)
    - Verifies coordinates are assigned for weather monitoring
    - Verifies consent_given and voice_alerts_enabled are True
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sync_resp = await client.post("/api/firebase/sync")
        assert sync_resp.status_code == 200
        sync_data = sync_resp.json()
        assert sync_data["success"] is True
        assert sync_data["total_synced"] >= 5

    # Verify directly in SQLite DB
    async with AsyncSessionLocal() as db:
        stmt = select(Farmer).where(Farmer.farmer_id.like("UZH-APP%"))
        res = await db.execute(stmt)
        farmers = res.scalars().all()
        assert len(farmers) >= 5

        # Check a specific app-registered farmer (e.g. Karthik Raja in Coimbatore)
        karthik = next((f for f in farmers if "Karthik" in f.name), None)
        assert karthik is not None
        assert karthik.district == "Coimbatore"
        assert karthik.main_crop == "Coconut"
        assert karthik.preferred_language == "ta-IN"
        assert karthik.consent_given is True
        assert karthik.voice_alerts_enabled is True
        assert karthik.latitude > 0.0 and karthik.longitude > 0.0

@pytest.mark.asyncio
async def test_mobile_app_registration_webhook():
    """
    Validates zero-modification integration for the mobile app:
    When the mobile app submits registration to POST /api/v2/auth/register,
    it automatically populates the farmer in the portal DB and enables voice calls.
    """
    unique_phone = f"+9198{random.randint(10000000, 99999999)}"
    payload = {
        "name": "Murugesan P",
        "phone": unique_phone,
        "language": "tamil",
        "district": "Salem",
        "location": "Attur",
        "state": "Tamil Nadu",
        "crop_type": "Tapioca",
        "soil_type": "Red Gravel",
        "user_type": "farmer"
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v2/auth/register", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        assert data["user"]["name"] == "Murugesan P"
        assert data["user"]["voice_alerts_enabled"] is True

    # Verify farmer exists in database with mapped coordinates
    async with AsyncSessionLocal() as db:
        stmt = select(Farmer).where(Farmer.phone == unique_phone)
        res = await db.execute(stmt)
        farmer = res.scalars().first()
        assert farmer is not None
        assert farmer.district == "Salem"
        assert farmer.main_crop == "Tapioca"
        assert farmer.preferred_language == "ta-IN"
        assert farmer.latitude == 11.6643  # Salem centroid
        assert farmer.voice_alerts_enabled is True

@pytest.mark.asyncio
async def test_autonomous_calling_expansion_for_app_farmers():
    """
    Requirement 3: App-registered farmers must receive automated voice calls
    based on their synced location and crop data.
    """
    async with AsyncSessionLocal() as db:
        # Create an app farmer registered in Pollachi / Coimbatore growing Coconut
        test_phone = f"+9197{uuid.uuid4().hex[:8]}"
        app_farmer = Farmer(
            farmer_id=f"UZH-APP-{uuid.uuid4().hex[:6].upper()}",
            name="Venkatesh S",
            phone=test_phone,
            preferred_language="ta-IN",
            farmer_category="Small",
            state="Tamil Nadu",
            district="Coimbatore",
            taluk="Pollachi",
            village="Pollachi",
            latitude=10.6609,
            longitude=77.0089,
            main_crop="Coconut",
            consent_given=True,
            voice_alerts_enabled=True
        )
        db.add(app_farmer)
        await db.commit()
        await db.refresh(app_farmer)

        # Trigger weather alert for Coimbatore
        event_id = f"COIMBATORE_HEAT_{uuid.uuid4().hex[:8]}"
        heat_alert = AgriculturalAlert(
            alert_id=f"ALT-HEAT-{uuid.uuid4().hex[:6].upper()}",
            event_id=event_id,
            alert_type="WEATHER",
            title="Heat Wave Warning for Coimbatore",
            severity="HIGH",
            state="Tamil Nadu",
            district="Coimbatore",
            crop="Coconut",
            summary_text="Severe heat wave expected in Coimbatore. Extra irrigation advised for coconut plantations.",
            content_json=json.dumps({"temp_max": 42.5})
        )
        db.add(heat_alert)
        await db.commit()
        await db.refresh(heat_alert)

        # Evaluate and queue via Decision Engine
        jobs = await DecisionEngine.process_and_queue_alert(db, heat_alert, {"temp_max": 42.5})
        assert len(jobs) > 0

        # Find the specific job for Venkatesh
        venkatesh_job = next((j for j in jobs if j.farmer_id == app_farmer.id), None)
        assert venkatesh_job is not None
        assert venkatesh_job.phone_number == test_phone
        assert venkatesh_job.language == "ta-IN"
        assert venkatesh_job.priority == "HIGH"
        assert venkatesh_job.status == "QUEUED"

        # Execute call job and verify call dispatch + audio synthesis
        call_success = await execute_call_job_async(venkatesh_job.job_id)
        assert call_success is True

        # Verify CallLog entry
        log_stmt = select(CallLog).where(CallLog.job_id == venkatesh_job.job_id)
        res = await db.execute(log_stmt)
        call_log = res.scalars().first()
        assert call_log is not None
        assert call_log.status in ("CALL_STARTED", "IN_PROGRESS", "ANSWERED", "COMPLETED")
        assert "உழவன் AI" in call_log.transcript_text or "Uzhavan" in call_log.transcript_text

@pytest.mark.asyncio
async def test_deduplication_on_resync():
    """Ensures repeated Firebase sync cycles do not duplicate existing farmers"""
    async with AsyncSessionLocal() as db:
        stmt_before = select(Farmer)
        count_before = len((await db.execute(stmt_before)).scalars().all())

        # Perform sync
        res1 = await FirebaseService.sync_app_registered_farmers(db)
        assert res1["success"] is True

        stmt_after1 = select(Farmer)
        count_after1 = len((await db.execute(stmt_after1)).scalars().all())

        # Perform sync again immediately
        res2 = await FirebaseService.sync_app_registered_farmers(db)
        assert res2["success"] is True

        stmt_after2 = select(Farmer)
        count_after2 = len((await db.execute(stmt_after2)).scalars().all())

        # Count should remain unchanged (no duplicates created)
        assert count_after1 == count_after2
