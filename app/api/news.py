import json
import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import AgriculturalAlert
from app.models.news import AgriculturalNews
from app.services.news_service import NewsService
from app.services.decision_engine import DecisionEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agricultural-news", tags=["Agricultural News"])

@router.get("")
async def get_agricultural_news(
    state: Optional[str] = Query("tamil_nadu"),
    language: Optional[str] = Query("english"),
    min_score: int = Query(60, description="Minimum relevance score threshold"),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches REAL agricultural news from verified sources (The Hindu, TOI, Asianet News).
    Filters out irrelevant/entertainment articles.
    """
    try:
        articles = await NewsService.fetch_agricultural_news(state=state, language=language)
        filtered = [a for a in articles if a.get("relevance_score", 0) >= min_score]
        return {
            "success": True,
            "count": len(filtered),
            "state": state,
            "news": filtered
        }
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/broadcast-news")
async def broadcast_news_alert(
    title: str,
    summary: str,
    district: Optional[str] = None,
    crop: Optional[str] = None,
    source: str = "TNAU / Govt Agriculture Dept",
    db: AsyncSession = Depends(get_db)
):
    """
    Broadcasts a high-priority agricultural department news announcement
    to matched farmers via the Decision Engine.
    """
    event_id = f"NEWS_{uuid.uuid4().hex[:8].upper()}"
    alert = AgriculturalAlert(
        alert_id=f"ALT-NWS-{uuid.uuid4().hex[:8].upper()}",
        event_id=event_id,
        alert_type="NEWS",
        title=title,
        severity="LOW",
        state="Tamil Nadu",
        district=district,
        crop=crop,
        summary_text=f"{title}: {summary}",
        content_json=json.dumps({"title": title, "summary": summary, "source": source})
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    queued = await DecisionEngine.process_and_queue_alert(
        db=db,
        alert=alert,
        alert_data={"news_title": title, "summary": summary}
    )

    return {
        "success": True,
        "alert_id": alert.alert_id,
        "event_id": alert.event_id,
        "queued_calls": len(queued),
        "job_ids": [j.job_id for j in queued]
    }
