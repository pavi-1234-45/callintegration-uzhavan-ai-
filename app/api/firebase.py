import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.firebase_service import FirebaseService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Firebase Integration"])

@router.post("/api/firebase/sync")
async def trigger_firebase_sync(db: AsyncSession = Depends(get_db)):
    """
    Manually or programmatically triggers a synchronization cycle with the
    Uzhavan AI Mobile App's Firebase backend.
    Fetches registered farmers, normalizes coordinates & language, saves to database,
    and enqueues autonomous calls for active agricultural alerts.
    """
    result = await FirebaseService.sync_app_registered_farmers(db)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Firebase sync failed"))
    return result

@router.get("/api/firebase/status")
async def get_firebase_status():
    """
    Returns current connection status and sync statistics for the
    Uzhavan AI Mobile App Firebase backend (Project: uzhavan-ai-686d6).
    """
    return FirebaseService.get_sync_status()

# -----------------------------------------------------------------------------
# Mobile App Native Integration Endpoint
# -----------------------------------------------------------------------------
@router.post("/api/v2/auth/register")
async def mobile_app_register_endpoint(
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Natively receives registration payloads dispatched by the Uzhavan AI Mobile App.
    Seamlessly populates the farmer in the voice portal database and enrolls them
    into the autonomous voice communication queue without requiring ANY changes
    to the mobile app.
    """
    logger.info(f"Received mobile app registration payload: {payload.get('name', 'Unknown')}")
    result = await FirebaseService.register_mobile_app_farmer(payload, db)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.get("/api/v2/auth/me")
async def mobile_app_me_endpoint():
    """
    Profile check endpoint for compatibility with mobile app.
    """
    return {
        "authenticated": True,
        "service": "Uzhavan AI Mobile App Sync Service",
        "firebase_project": "uzhavan-ai-686d6"
    }
