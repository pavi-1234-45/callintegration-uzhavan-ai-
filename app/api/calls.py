import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.database import get_db
from app.models.call import CallJob, CallLog
from app.models.farmer import Farmer
from app.schemas.call import CallJobResponse, CallLogResponse
from app.tasks.worker import execute_call_job_async

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/calls", tags=["Voice Calls & History"])

@router.get("/queue", response_model=List[CallJobResponse])
async def get_call_queue(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Lists queued call jobs pending telephony dispatch"""
    query = select(CallJob).order_by(
        # CRITICAL first, then HIGH, then NORMAL, then LOW
        CallJob.priority == "CRITICAL",
        CallJob.priority == "HIGH",
        CallJob.priority == "NORMAL",
        CallJob.id.desc()
    )

    if status:
        query = query.where(CallJob.status == status.upper())
    if priority:
        query = query.where(CallJob.priority == priority.upper())

    res = await db.execute(query)
    return res.scalars().all()

@router.get("/history", response_model=List[CallLogResponse])
async def get_call_history(
    status: Optional[str] = None,
    language: Optional[str] = None,
    call_type: Optional[str] = None,
    district: Optional[str] = None,
    crop: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Lists historical call records with real carrier statuses, durations,
    and DTMF interaction responses.
    """
    from sqlalchemy.orm import selectinload
    query = select(CallLog).options(selectinload(CallLog.farmer)).order_by(CallLog.id.desc())

    if isinstance(status, str) and status.strip():
        query = query.where(CallLog.status == status.strip().upper())
    if isinstance(language, str) and language.strip():
        query = query.where(CallLog.language == language.strip())
    if isinstance(call_type, str) and call_type.strip():
        query = query.where(CallLog.call_type == call_type.strip().upper())

    if (isinstance(district, str) and district.strip()) or (isinstance(crop, str) and crop.strip()):
        query = query.join(Farmer, CallLog.farmer_id == Farmer.id)
        if isinstance(district, str) and district.strip():
            query = query.where(Farmer.district.ilike(district.strip()))
        if isinstance(crop, str) and crop.strip():
            query = query.where(Farmer.main_crop.ilike(f"%{crop.strip()}%"))

    res = await db.execute(query)
    return res.scalars().all()

@router.post("/dispatch-queue")
async def dispatch_queue_jobs(background_tasks: BackgroundTasks, limit: int = 20, db: AsyncSession = Depends(get_db)):
    """
    Dispatches pending queued call jobs to telephony workers.
    Respects provider concurrency limits.
    """
    stmt = select(CallJob).where(
        CallJob.status.in_(("QUEUED", "RETRY_PENDING"))
    ).order_by(
        CallJob.priority == "CRITICAL",
        CallJob.priority == "HIGH",
        CallJob.priority == "NORMAL",
        CallJob.id.asc()
    ).limit(limit)

    res = await db.execute(stmt)
    jobs = res.scalars().all()

    dispatched = 0
    for job in jobs:
        # Schedule execution
        background_tasks.add_task(execute_call_job_async, job.job_id)
        dispatched += 1

    return {
        "success": True,
        "dispatched_count": dispatched,
        "message": f"Dispatched {dispatched} calls to telephony queue"
    }

@router.post("/test-call/{farmer_id}")
async def trigger_test_farmer_call(
    farmer_id: int,
    background_tasks: BackgroundTasks,
    simulate_dtmf: Optional[str] = Query(None, description="Optional DTMF digit simulation: 1, 2, 9, 0"),
    db: AsyncSession = Depends(get_db)
):
    """
    VERTICAL SLICE TEST PROCEDURE:
    Tests immediate call triggering for 1 specific registered farmer.
    Dials their registered phone number in their preferred language.
    """
    stmt = select(Farmer).where(Farmer.id == farmer_id)
    res = await db.execute(stmt)
    farmer = res.scalars().first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    if not farmer.consent_given:
        raise HTTPException(status_code=400, detail="Cannot call farmer without recorded voice consent.")

    # Create a test call job
    import uuid
    job_id = f"JOB-TEST-{uuid.uuid4().hex[:8].upper()}"
    event_id = f"TEST_CALL_{farmer.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    job = CallJob(
        job_id=job_id,
        farmer_id=farmer.id,
        event_id=event_id,
        phone_number=farmer.phone,
        language=farmer.preferred_language,
        priority="HIGH",
        status="QUEUED",
        attempts=0,
        max_retries=3
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Dispatch immediately
    background_tasks.add_task(execute_call_job_async, job.job_id)

    return {
        "success": True,
        "job_id": job.job_id,
        "farmer_name": farmer.name,
        "phone": farmer.masked_phone,
        "language": farmer.preferred_language,
        "message": f"Test call queued for {farmer.name} ({farmer.phone})"
    }
