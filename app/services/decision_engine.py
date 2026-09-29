import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.farmer import Farmer
from app.models.alert import AgriculturalAlert
from app.models.call import CallJob, CallLog

logger = logging.getLogger(__name__)

class DecisionEngine:
    @staticmethod
    async def match_farmers_for_alert(
        db: AsyncSession,
        alert_type: str, # WEATHER, MARKET, SCHEME, NEWS
        event_id: str,
        district: Optional[str] = None,
        crop: Optional[str] = None,
        state: Optional[str] = None,
        farmer_category: Optional[str] = None
    ) -> List[Farmer]:
        """
        Identifies eligible registered farmers who:
        1. Have given consent for voice calls (consent_given == True)
        2. Have active voice alerts enabled (voice_alerts_enabled == True)
        3. Match location and crop criteria
        """
        query = select(Farmer).where(
            Farmer.consent_given == True,
            Farmer.voice_alerts_enabled == True
        )

        # State filter
        if state and state.lower() not in ("all", "all india"):
            query = query.where(Farmer.state.ilike(state))

        # District filter
        if district and district.lower() not in ("all", "all districts"):
            query = query.where(Farmer.district.ilike(district))

        result = await db.execute(query)
        candidates = result.scalars().all()

        matched_farmers = []
        for farmer in candidates:
            # Crop matching (mandatory for market alerts, optional for general weather unless crop-specific)
            if crop and crop.lower() not in ("all", "any"):
                farmer_crops = [farmer.main_crop.strip().lower()]
                if farmer.additional_crops:
                    farmer_crops.extend([c.strip().lower() for c in farmer.additional_crops.split(",")])

                crop_match = any(crop.strip().lower() in fc or fc in crop.strip().lower() for fc in farmer_crops)
                if not crop_match:
                    continue

            # Farmer category matching for schemes
            if farmer_category and farmer_category.lower() not in ("all", "any"):
                if farmer.farmer_category and farmer.farmer_category.lower() != farmer_category.lower():
                    continue

            matched_farmers.append(farmer)

        return matched_farmers

    @staticmethod
    async def is_duplicate_alert(db: AsyncSession, farmer_id: int, event_id: str) -> bool:
        """
        Mandatory duplicate prevention:
        Checks if the farmer has already received or been queued for this deterministic event ID.
        """
        # 1. Check existing call jobs
        job_stmt = select(CallJob).where(
            CallJob.farmer_id == farmer_id,
            CallJob.event_id == event_id
        )
        job_res = await db.execute(job_stmt)
        if job_res.scalars().first():
            return True

        # 2. Check completed/historical call logs
        log_stmt = select(CallLog).where(
            CallLog.farmer_id == farmer_id,
            CallLog.event_id == event_id
        )
        log_res = await db.execute(log_stmt)
        if log_res.scalars().first():
            return True

        return False

    @staticmethod
    async def process_and_queue_alert(
        db: AsyncSession,
        alert: AgriculturalAlert,
        alert_data: Dict[str, Any]
    ) -> List[CallJob]:
        """
        Evaluates affected farmers, performs duplicate check, assesses quiet hours,
        and creates prioritized CallJob records in the queue.
        """
        matched = await DecisionEngine.match_farmers_for_alert(
            db=db,
            alert_type=alert.alert_type,
            event_id=alert.event_id,
            district=alert.district,
            crop=alert.crop,
            state=alert.state
        )

        logger.info(f"Decision Engine: Alert {alert.event_id} ({alert.alert_type}, {alert.severity}) matched {len(matched)} farmers.")

        created_jobs = []
        is_quiet = settings.is_in_quiet_hours(alert.severity)

        for farmer in matched:
            # Duplicate check
            already_processed = await DecisionEngine.is_duplicate_alert(db, farmer.id, alert.event_id)
            if already_processed:
                logger.info(f"Skipping duplicate alert {alert.event_id} for Farmer {farmer.name} ({farmer.phone})")
                continue

            # Schedule time handling for quiet hours
            scheduled_time = datetime.utcnow()
            if is_quiet:
                # Schedule after quiet hours end in local morning (06:00 AM)
                scheduled_time = scheduled_time + timedelta(hours=8)
                logger.info(f"Quiet hours active: Queuing job for Farmer {farmer.name} scheduled for {scheduled_time.isoformat()}")

            job = CallJob(
                job_id=f"JOB-{uuid.uuid4().hex[:10].upper()}",
                farmer_id=farmer.id,
                alert_id=alert.id,
                event_id=alert.event_id,
                phone_number=farmer.phone,
                language=farmer.preferred_language,
                priority=alert.severity,
                status="QUEUED",
                attempts=0,
                max_retries=settings.MAX_RETRIES,
                scheduled_for=scheduled_time
            )
            db.add(job)
            created_jobs.append(job)

        if created_jobs:
            await db.commit()
            for job in created_jobs:
                await db.refresh(job)

        return created_jobs
