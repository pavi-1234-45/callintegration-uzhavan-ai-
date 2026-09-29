import json
import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import AgriculturalAlert
from app.models.market import MarketPriceUpdate
from app.services.market_service import MarketService
from app.services.decision_engine import DecisionEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/market-updates", tags=["Market Updates"])

@router.get("")
async def get_market_updates(
    state: Optional[str] = Query("Tamil Nadu"),
    crop: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches real agricultural market prices from live Agmarknet / Uzhavan API.
    Optionally stores latest prices in database.
    """
    try:
        prices = await MarketService.fetch_market_prices(state=state, crop=crop)
        return {
            "success": True,
            "count": len(prices),
            "state": state,
            "prices": prices
        }
    except Exception as e:
        logger.error(f"Error fetching market updates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/broadcast-crop-price")
async def broadcast_crop_price(crop: str, state: str = "Tamil Nadu", db: AsyncSession = Depends(get_db)):
    """
    Fetches the real price for a specific crop and triggers autonomous calls
    ONLY to farmers registered for that specific crop.
    """
    prices = await MarketService.fetch_market_prices(state=state, crop=crop)
    if not prices:
        raise HTTPException(status_code=404, detail=f"No active market prices found for crop '{crop}'")

    item = prices[0]
    alert_info = MarketService.generate_market_alert(item)
    event_id = alert_info["event_id"]

    stmt = select(AgriculturalAlert).where(AgriculturalAlert.event_id == event_id)
    res = await db.execute(stmt)
    alert = res.scalars().first()

    if not alert:
        alert = AgriculturalAlert(
            alert_id=f"ALT-MKT-{uuid.uuid4().hex[:8].upper()}",
            event_id=event_id,
            alert_type="MARKET",
            title=alert_info["title"],
            severity="NORMAL",
            state=state,
            crop=item.get("commodity"),
            summary_text=alert_info["summary"],
            content_json=json.dumps(alert_info)
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)

    queued = await DecisionEngine.process_and_queue_alert(db, alert, alert_info)

    return {
        "success": True,
        "crop": item.get("commodity"),
        "modal_price": item.get("modal_price"),
        "unit": item.get("unit"),
        "queued_calls": len(queued),
        "job_ids": [j.job_id for j in queued]
    }
