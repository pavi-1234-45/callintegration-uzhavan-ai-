import uuid
import datetime
import httpx
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.farmer import Farmer
from app.schemas.farmer import FarmerCreate, FarmerUpdate, FarmerResponse, FarmerRegistrationConfirmation
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/farmers", tags=["Farmers"])

@router.post("", response_model=FarmerRegistrationConfirmation, status_code=201)
async def register_farmer(farmer_in: FarmerCreate, db: AsyncSession = Depends(get_db)):
    """
    Registers a new farmer from the field survey form.
    Validates phone number, preferred language, crop, location, and consent.
    NOTE: Does NOT trigger an immediate phone call. Registration enables future relevant alerts.
    """
    # Check if phone number already registered
    existing_stmt = select(Farmer).where(Farmer.phone == farmer_in.phone)
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalars().first():
        raise HTTPException(status_code=400, detail=f"Phone number {farmer_in.phone} is already registered.")

    # Generate sequential or unique Farmer ID: e.g. UZH-FARM-00123
    count_stmt = select(Farmer)
    all_res = await db.execute(count_stmt)
    total_count = len(all_res.scalars().all())
    farmer_id = f"UZH-FARM-{10001 + total_count}"

    consent_ts = datetime.datetime.utcnow() if farmer_in.consent_given else None
    voice_enabled = farmer_in.voice_alerts_enabled if farmer_in.consent_given else False

    farmer = Farmer(
        farmer_id=farmer_id,
        name=farmer_in.name.strip(),
        phone=farmer_in.phone,
        preferred_language=farmer_in.preferred_language,
        farmer_category=farmer_in.farmer_category,
        state=farmer_in.state.strip(),
        district=farmer_in.district.strip(),
        taluk=farmer_in.taluk.strip() if farmer_in.taluk else None,
        village=farmer_in.village.strip() if farmer_in.village else None,
        latitude=farmer_in.latitude,
        longitude=farmer_in.longitude,
        main_crop=farmer_in.main_crop.strip(),
        additional_crops=farmer_in.additional_crops.strip() if farmer_in.additional_crops else "",
        crop_season=farmer_in.crop_season,
        consent_given=farmer_in.consent_given,
        consent_timestamp=consent_ts,
        voice_alerts_enabled=voice_enabled
    )

    db.add(farmer)
    await db.commit()
    await db.refresh(farmer)

    lang_name = settings.SUPPORTED_LANGUAGES.get(farmer.preferred_language, {}).get("name", farmer.preferred_language)

    return FarmerRegistrationConfirmation(
        success=True,
        message="Farmer Registered Successfully",
        farmer_id=farmer.farmer_id,
        name=farmer.name,
        masked_phone=farmer.masked_phone,
        location=f"{farmer.district}, {farmer.state}",
        crop=farmer.main_crop,
        language=lang_name,
        voice_alerts="Enabled" if farmer.voice_alerts_enabled else "Disabled",
        registered_at=farmer.created_at
    )

@router.get("", response_model=List[FarmerResponse])
async def list_farmers(
    search: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    crop: Optional[str] = None,
    language: Optional[str] = None,
    voice_status: Optional[str] = None, # enabled, disabled
    source: Optional[str] = None, # mobile_app, survey_portal
    db: AsyncSession = Depends(get_db)
):
    """Lists registered farmers with optional search and filters"""
    query = select(Farmer).order_by(Farmer.id.desc())

    if isinstance(search, str) and search.strip():
        s = f"%{search.strip()}%"
        query = query.where(
            or_(
                Farmer.name.ilike(s),
                Farmer.farmer_id.ilike(s),
                Farmer.phone.ilike(s)
            )
        )

    if isinstance(state, str) and state.strip():
        query = query.where(Farmer.state.ilike(state.strip()))
    if isinstance(district, str) and district.strip():
        query = query.where(Farmer.district.ilike(district.strip()))
    if isinstance(crop, str) and crop.strip():
        query = query.where(Farmer.main_crop.ilike(f"%{crop.strip()}%"))
    if isinstance(language, str) and language.strip():
        query = query.where(Farmer.preferred_language == language.strip())
    if isinstance(voice_status, str) and voice_status.strip():
        if voice_status.lower() == "enabled":
            query = query.where(Farmer.voice_alerts_enabled == True)
        elif voice_status.lower() == "disabled":
            query = query.where(Farmer.voice_alerts_enabled == False)
    if isinstance(source, str) and source.strip():
        query = query.where(Farmer.source == source.strip())

    res = await db.execute(query)
    farmers = res.scalars().all()
    return farmers

@router.get("/{id}", response_model=FarmerResponse)
async def get_farmer(id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Farmer).where(Farmer.id == id)
    res = await db.execute(stmt)
    farmer = res.scalars().first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")
    return farmer

@router.put("/{id}", response_model=FarmerResponse)
async def update_farmer(id: int, update_data: FarmerUpdate, db: AsyncSession = Depends(get_db)):
    """Updates farmer preferences, location, or crop"""
    stmt = select(Farmer).where(Farmer.id == id)
    res = await db.execute(stmt)
    farmer = res.scalars().first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    for field, val in update_data.model_dump(exclude_unset=True).items():
        setattr(farmer, field, val)

    # Re-evaluate voice alerts if consent altered
    if update_data.consent_given is not None:
        if update_data.consent_given:
            farmer.consent_timestamp = datetime.datetime.utcnow()
        else:
            farmer.voice_alerts_enabled = False

    farmer.updated_at = datetime.datetime.utcnow()
    await db.commit()
    await db.refresh(farmer)
    return farmer

@router.post("/{id}/toggle-voice")
async def toggle_voice_alerts(id: int, db: AsyncSession = Depends(get_db)):
    """Toggles voice alert status for a farmer"""
    stmt = select(Farmer).where(Farmer.id == id)
    res = await db.execute(stmt)
    farmer = res.scalars().first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    if not farmer.consent_given:
        raise HTTPException(status_code=400, detail="Cannot enable voice alerts without recorded consent.")

    farmer.voice_alerts_enabled = not farmer.voice_alerts_enabled
    await db.commit()
    return {
        "farmer_id": farmer.farmer_id,
        "voice_alerts_enabled": farmer.voice_alerts_enabled,
        "message": f"Voice alerts {'enabled' if farmer.voice_alerts_enabled else 'disabled'}"
    }

@router.get("/tools/reverse-geocode")
async def reverse_geocode(lat: float, lon: float):
    """
    Utility for Field Staff: Automatically detects District, Taluk, and State
    from GPS coordinates using OpenStreetMap Nominatim.
    """
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1"
        headers = {"User-Agent": "UzhavanAIVoiceSystem/1.0 (agri@uzhavan.ai)"}
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                address = data.get("address", {})
                district = address.get("state_district") or address.get("county") or address.get("city") or "Madurai"
                state = address.get("state", "Tamil Nadu")
                taluk = address.get("subdistrict") or address.get("county") or ""
                village = address.get("village") or address.get("suburb") or address.get("hamlet") or ""
                return {
                    "success": True,
                    "district": district,
                    "state": state,
                    "taluk": taluk,
                    "village": village,
                    "display_name": data.get("display_name")
                }
    except Exception as e:
        logger.warning(f"Reverse geocode lookup warning: {e}")

    return {
        "success": False,
        "district": "",
        "state": "Tamil Nadu",
        "taluk": "",
        "village": ""
    }
