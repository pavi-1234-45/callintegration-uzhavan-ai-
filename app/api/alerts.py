import uuid
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import AgriculturalAlert
from app.schemas.alert import AlertCreate, AlertResponse
from app.services.weather_service import WeatherService
from app.services.decision_engine import DecisionEngine
from app.tasks.worker import execute_call_job_async

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alerts", tags=["Agricultural Alerts"])

class WeatherTriggerRequest(BaseModel):
    district: str
    latitude: float
    longitude: float
    state: Optional[str] = "Tamil Nadu"

@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    alert_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    query = select(AgriculturalAlert).order_by(AgriculturalAlert.id.desc())
    if alert_type:
        query = query.where(AgriculturalAlert.alert_type == alert_type.upper())
    if severity:
        query = query.where(AgriculturalAlert.severity == severity.upper())
    if district:
        query = query.where(AgriculturalAlert.district.ilike(district))

    res = await db.execute(query)
    return res.scalars().all()

@router.post("/trigger-weather-check")
async def trigger_weather_check(req: WeatherTriggerRequest, db: AsyncSession = Depends(get_db)):
    """
    Fetches REAL weather data for the specified coordinates,
    evaluates deterministic alert criteria, records alert in DB,
    and runs the Decision Engine to match and queue calls for affected farmers.
    """
    try:
        weather_data = await WeatherService.fetch_weather_data(req.latitude, req.longitude, req.district)
        severity, condition, event_id, desc = WeatherService.evaluate_weather_alert(req.district, weather_data)

        # Check existing alert
        stmt = select(AgriculturalAlert).where(AgriculturalAlert.event_id == event_id)
        res = await db.execute(stmt)
        alert = res.scalars().first()

        is_new_alert = False
        if not alert:
            is_new_alert = True
            alert = AgriculturalAlert(
                alert_id=f"ALT-WTH-{uuid.uuid4().hex[:8].upper()}",
                event_id=event_id,
                alert_type="WEATHER",
                title=f"{condition.replace('_', ' ').title()} Alert for {req.district}",
                severity=severity,
                state=req.state,
                district=req.district,
                summary_text=desc,
                content_json=json.dumps(weather_data)
            )
            db.add(alert)
            await db.commit()
            await db.refresh(alert)

        queued_jobs = []
        if severity != "NO_ALERT":
            queued_jobs = await DecisionEngine.process_and_queue_alert(db, alert, weather_data)

        return {
            "success": True,
            "district": req.district,
            "weather_data": {
                "temperature": weather_data.get("temperature"),
                "rain_sum": weather_data.get("precipitation_sum"),
                "rain_probability": weather_data.get("rain_probability"),
                "wind_speed": weather_data.get("wind_speed")
            },
            "evaluation": {
                "severity": severity,
                "condition": condition,
                "event_id": event_id,
                "description": desc
            },
            "alert_created": is_new_alert,
            "queued_call_jobs": len(queued_jobs),
            "job_ids": [j.job_id for j in queued_jobs]
        }
    except Exception as e:
        logger.error(f"Weather trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/manual-emergency")
async def create_manual_emergency_alert(
    title: str,
    district: str,
    severity: str = "HIGH", # CRITICAL or HIGH
    crop: Optional[str] = None,
    summary: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Allows field admin to issue a critical localized warning to farmers"""
    event_id = f"MANUAL_{district.upper()}_{uuid.uuid4().hex[:6].upper()}"
    alert = AgriculturalAlert(
        alert_id=f"ALT-MAN-{uuid.uuid4().hex[:8].upper()}",
        event_id=event_id,
        alert_type="WEATHER" if "rain" in title.lower() else "NEWS",
        title=title,
        severity=severity.upper(),
        state="Tamil Nadu",
        district=district,
        crop=crop,
        summary_text=summary or title,
        content_json=json.dumps({"title": title, "district": district, "crop": crop})
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    queued = await DecisionEngine.process_and_queue_alert(db, alert, {"title": title})

    return {
        "success": True,
        "alert_id": alert.alert_id,
        "event_id": alert.event_id,
        "queued_calls": len(queued),
        "job_ids": [j.job_id for j in queued]
    }
