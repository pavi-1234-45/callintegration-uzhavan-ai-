from datetime import datetime, date
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.farmer import Farmer
from app.models.alert import AgriculturalAlert
from app.models.call import CallJob, CallLog

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/stats")
async def get_dashboard_stats(
    district: Optional[str] = None,
    crop: Optional[str] = None,
    language: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Computes REAL database metric counts for portal dashboard.
    Strictly displays real counts; 0 if empty.
    """
    # 1. Total Farmers
    f_query = select(func.count(Farmer.id))
    if isinstance(district, str) and district:
        f_query = f_query.where(Farmer.district.ilike(district))
    if isinstance(crop, str) and crop:
        f_query = f_query.where(Farmer.main_crop.ilike(f"%{crop}%"))
    if isinstance(language, str) and language:
        f_query = f_query.where(Farmer.preferred_language == language)
    total_farmers = (await db.execute(f_query)).scalar() or 0

    # 2. Voice-Enabled Farmers
    v_query = select(func.count(Farmer.id)).where(
        Farmer.voice_alerts_enabled == True,
        Farmer.consent_given == True
    )
    if isinstance(district, str) and district:
        v_query = v_query.where(Farmer.district.ilike(district))
    if isinstance(crop, str) and crop:
        v_query = v_query.where(Farmer.main_crop.ilike(f"%{crop}%"))
    if isinstance(language, str) and language:
        v_query = v_query.where(Farmer.preferred_language == language)
    voice_enabled_farmers = (await db.execute(v_query)).scalar() or 0

    # 3. Today's Alerts
    today_start = datetime.combine(date.today(), datetime.min.time())
    a_query = select(func.count(AgriculturalAlert.id)).where(
        AgriculturalAlert.created_at >= today_start
    )
    if isinstance(district, str) and district:
        a_query = a_query.where(AgriculturalAlert.district.ilike(district))
    if isinstance(crop, str) and crop:
        a_query = a_query.where(AgriculturalAlert.crop.ilike(f"%{crop}%"))
    todays_alerts = (await db.execute(a_query)).scalar() or 0

    # 4. Queued Calls
    q_query = select(func.count(CallJob.id)).where(CallJob.status == "QUEUED")
    queued_calls = (await db.execute(q_query)).scalar() or 0

    # 5. Completed Calls
    comp_query = select(func.count(CallLog.id)).where(CallLog.status == "COMPLETED")
    completed_calls = (await db.execute(comp_query)).scalar() or 0

    # 6. Failed Calls
    fail_query = select(func.count(CallLog.id)).where(CallLog.status == "FAILED")
    failed_calls = (await db.execute(fail_query)).scalar() or 0

    # 7. No-Answer Calls
    no_ans_query = select(func.count(CallLog.id)).where(CallLog.status == "NO_ANSWER")
    no_answer_calls = (await db.execute(no_ans_query)).scalar() or 0

    # 8. Active Retries
    retry_query = select(func.count(CallJob.id)).where(CallJob.status == "RETRY_PENDING")
    active_retries = (await db.execute(retry_query)).scalar() or 0

    # Recent Alerts
    recent_alerts_stmt = select(AgriculturalAlert).order_by(AgriculturalAlert.id.desc()).limit(5)
    recent_alerts = (await db.execute(recent_alerts_stmt)).scalars().all()

    # Recent Call Logs
    recent_calls_stmt = select(CallLog).order_by(CallLog.id.desc()).limit(8)
    recent_calls = (await db.execute(recent_calls_stmt)).scalars().all()

    return {
        "total_farmers": total_farmers,
        "voice_enabled_farmers": voice_enabled_farmers,
        "todays_alerts": todays_alerts,
        "queued_calls": queued_calls,
        "completed_calls": completed_calls,
        "failed_calls": failed_calls,
        "no_answer_calls": no_answer_calls,
        "active_retries": active_retries,
        "recent_alerts": [
            {
                "id": a.id,
                "title": a.title,
                "type": a.alert_type,
                "severity": a.severity,
                "district": a.district,
                "time": a.created_at.strftime("%H:%M, %d %b") if a.created_at else ""
            }
            for a in recent_alerts
        ],
        "recent_calls": [
            {
                "call_id": c.call_id,
                "phone": c.masked_phone,
                "status": c.status,
                "duration": c.duration,
                "dtmf": c.dtmf_response,
                "language": c.language,
                "time": c.created_at.strftime("%H:%M:%S") if c.created_at else ""
            }
            for c in recent_calls
        ]
    }
