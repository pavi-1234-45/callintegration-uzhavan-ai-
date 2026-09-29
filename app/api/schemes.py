import uuid
import json
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.scheme import GovernmentScheme
from app.models.alert import AgriculturalAlert
from app.schemas.scheme import GovernmentSchemeCreate, GovernmentSchemeVerify, GovernmentSchemeResponse
from app.services.scheme_service import SchemeService
from app.services.decision_engine import DecisionEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/schemes", tags=["Government Schemes"])

# Official government schemes seed data
OFFICIAL_SCHEMES_SEED = [
    {
        "scheme_name": "PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)",
        "description": "Income support of ₹6,000 per year in three equal installments to all landholding farmer families across the country.",
        "state": "All India",
        "district": "All",
        "eligible_crop": "All",
        "farmer_category": "Small,Marginal",
        "eligibility_criteria": "Small and marginal farmers owning cultivable land up to 2 hectares.",
        "benefit": "₹6,000 annually credited directly into farmer Aadhaar-linked bank accounts.",
        "start_date": "2026-01-01",
        "deadline": "2026-12-31",
        "official_url": "https://pmkisan.gov.in",
        "verification_status": "PUBLISHED",
        "verified_by": "Government Agriculture Portal Admin"
    },
    {
        "scheme_name": "Pradhan Mantri Fasal Bima Yojana (PMFBY)",
        "description": "Comprehensive crop insurance scheme providing financial support to farmers suffering crop loss or damage arising from unforeseen weather events.",
        "state": "Tamil Nadu",
        "district": "All",
        "eligible_crop": "Paddy,Tomato,Cotton,Groundnut,Maize",
        "farmer_category": "All",
        "eligibility_criteria": "All farmers growing notified crops in notified areas including sharecroppers and tenant farmers.",
        "benefit": "Subsidized premium (1.5% - 2%) with full financial compensation for yield loss due to floods or drought.",
        "start_date": "2026-06-01",
        "deadline": "2026-11-30",
        "official_url": "https://pmfby.gov.in",
        "verification_status": "PUBLISHED",
        "verified_by": "State Nodal Officer"
    },
    {
        "scheme_name": "Tamil Nadu Micro Irrigation Scheme (Per Drop More Crop)",
        "description": "Special state subsidy scheme offering drip and sprinkler irrigation units to conserve water and improve horticultural crop yields.",
        "state": "Tamil Nadu",
        "district": "Madurai,Thanjavur,Coimbatore,Salem,Dindigul",
        "eligible_crop": "Tomato,Brinjal,Chilli,Banana,Sugarcane",
        "farmer_category": "Small,Marginal",
        "eligibility_criteria": "Small and marginal farmers with verified land pattas and functional borewell/open well irrigation source.",
        "benefit": "100% subsidy for small/marginal farmers and 75% subsidy for other farmers on micro-irrigation installation.",
        "start_date": "2026-04-01",
        "deadline": "2026-10-31",
        "official_url": "https://tnhorticulture.tn.gov.in",
        "verification_status": "PUBLISHED",
        "verified_by": "Director of Horticulture, TN"
    },
    {
        "scheme_name": "Kalaignar All Village Integrated Agriculture Development Programme",
        "description": "Flagship Tamil Nadu rural development program distributing free tarpaulins, hand/power sprayers, pulse seed mini-kits, and tree saplings.",
        "state": "Tamil Nadu",
        "district": "All",
        "eligible_crop": "Paddy,Millets,Pulses,Tomato,Vegetables",
        "farmer_category": "Small,Marginal",
        "eligibility_criteria": "Farmers resident in designated village panchayats verified through Uzhavan App or Agrisnet.",
        "benefit": "Free high-density tarpaulins, power sprayers with 50% subsidy, and certified seed mini-kits.",
        "start_date": "2026-05-15",
        "deadline": "2026-11-15",
        "official_url": "https://agri.tn.gov.in",
        "verification_status": "PUBLISHED",
        "verified_by": "Agriculture Production Commissioner"
    }
]

@router.get("", response_model=List[GovernmentSchemeResponse])
async def list_schemes(
    status: Optional[str] = None,
    crop: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Lists government schemes; auto-seeds verified official schemes if empty"""
    stmt = select(GovernmentScheme).order_by(GovernmentScheme.id.desc())
    if isinstance(status, str) and status.strip():
        stmt = stmt.where(GovernmentScheme.verification_status == status.strip().upper())

    res = await db.execute(stmt)
    schemes = res.scalars().all()

    # Seed official schemes if table is empty
    if not schemes and not status:
        for s in OFFICIAL_SCHEMES_SEED:
            item = GovernmentScheme(
                scheme_name=s["scheme_name"],
                description=s["description"],
                state=s["state"],
                district=s["district"],
                eligible_crop=s["eligible_crop"],
                farmer_category=s["farmer_category"],
                eligibility_criteria=s["eligibility_criteria"],
                benefit=s["benefit"],
                start_date=s["start_date"],
                deadline=s["deadline"],
                official_url=s["official_url"],
                verification_status=s["verification_status"],
                verified_by=s["verified_by"],
                verified_at=datetime.utcnow()
            )
            db.add(item)
        await db.commit()
        res = await db.execute(stmt)
        schemes = res.scalars().all()

    return schemes

@router.post("", response_model=GovernmentSchemeResponse, status_code=201)
async def create_scheme(scheme_in: GovernmentSchemeCreate, db: AsyncSession = Depends(get_db)):
    """Creates a new government scheme entry requiring admin verification before broadcast"""
    scheme = GovernmentScheme(
        scheme_name=scheme_in.scheme_name,
        description=scheme_in.description,
        state=scheme_in.state,
        district=scheme_in.district,
        eligible_crop=scheme_in.eligible_crop,
        farmer_category=scheme_in.farmer_category,
        eligibility_criteria=scheme_in.eligibility_criteria,
        benefit=scheme_in.benefit,
        start_date=scheme_in.start_date,
        deadline=scheme_in.deadline,
        official_url=scheme_in.official_url,
        verification_status="PENDING_VERIFICATION"
    )
    db.add(scheme)
    await db.commit()
    await db.refresh(scheme)
    return scheme

@router.post("/{id}/verify")
async def verify_scheme(id: int, verify_in: GovernmentSchemeVerify, db: AsyncSession = Depends(get_db)):
    """
    Admin verification flow.
    When a scheme is marked PUBLISHED, the system autonomously identifies
    eligible registered farmers and queues voice calls.
    """
    stmt = select(GovernmentScheme).where(GovernmentScheme.id == id)
    res = await db.execute(stmt)
    scheme = res.scalars().first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")

    action = verify_in.action.upper()
    if action == "PUBLISH":
        scheme.verification_status = "PUBLISHED"
        scheme.verified_by = verify_in.verified_by
        scheme.verified_at = datetime.utcnow()
        await db.commit()
        await db.refresh(scheme)

        # Create AgriculturalAlert and trigger Decision Engine
        event_id = SchemeService.get_scheme_event_id(scheme)
        alert = AgriculturalAlert(
            alert_id=f"ALT-SCM-{uuid.uuid4().hex[:8].upper()}",
            event_id=event_id,
            alert_type="SCHEME",
            title=f"New Government Scheme: {scheme.scheme_name}",
            severity="NORMAL",
            state=scheme.state,
            district=scheme.district,
            crop=scheme.eligible_crop,
            summary_text=f"{scheme.scheme_name}: {scheme.benefit}. Apply before {scheme.deadline or 'closing date'}.",
            content_json=json.dumps({
                "scheme_name": scheme.scheme_name,
                "benefit": scheme.benefit,
                "deadline": scheme.deadline,
                "url": scheme.official_url
            })
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)

        queued = await DecisionEngine.process_and_queue_alert(
            db=db,
            alert=alert,
            alert_data={"scheme_name": scheme.scheme_name, "benefit": scheme.benefit}
        )

        return {
            "success": True,
            "status": "PUBLISHED",
            "message": f"Scheme verified and published. Queued voice calls for {len(queued)} eligible farmers.",
            "queued_calls": len(queued),
            "job_ids": [j.job_id for j in queued]
        }
    elif action == "VERIFY":
        scheme.verification_status = "VERIFIED"
        scheme.verified_by = verify_in.verified_by
        scheme.verified_at = datetime.utcnow()
        await db.commit()
        return {"success": True, "status": "VERIFIED", "message": "Scheme marked as verified."}
    elif action == "REJECT":
        scheme.verification_status = "REJECTED"
        await db.commit()
        return {"success": True, "status": "REJECTED", "message": "Scheme rejected."}
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use VERIFY, PUBLISH, or REJECT.")
