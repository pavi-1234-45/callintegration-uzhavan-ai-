import logging
from typing import Dict, Any, List
from datetime import datetime
from app.models.scheme import GovernmentScheme
from app.models.farmer import Farmer

logger = logging.getLogger(__name__)

class SchemeService:
    @staticmethod
    def is_farmer_eligible(farmer: Farmer, scheme: GovernmentScheme) -> bool:
        """
        Determines eligibility based on State, District, Crop, and Farmer Category.
        """
        # Verification check: only PUBLISHED schemes trigger calls
        if scheme.verification_status != "PUBLISHED":
            return False

        # State check
        if scheme.state != "All India" and scheme.state.lower() != farmer.state.lower():
            return False

        # District check
        if scheme.district and scheme.district != "All" and scheme.district.lower() != farmer.district.lower():
            return False

        # Crop check
        if scheme.eligible_crop and scheme.eligible_crop != "All":
            eligible_crops = [c.strip().lower() for c in scheme.eligible_crop.split(",")]
            farmer_crops = [farmer.main_crop.strip().lower()]
            if farmer.additional_crops:
                farmer_crops.extend([c.strip().lower() for c in farmer.additional_crops.split(",")])

            if not any(fc in eligible_crops for fc in farmer_crops):
                return False

        # Category check (Small, Marginal, Medium, Large)
        if scheme.farmer_category and scheme.farmer_category != "All":
            eligible_cats = [cat.strip().lower() for cat in scheme.farmer_category.split(",")]
            if farmer.farmer_category and farmer.farmer_category.lower() not in eligible_cats:
                return False

        return True

    @staticmethod
    def get_scheme_event_id(scheme: GovernmentScheme) -> str:
        name_clean = scheme.scheme_name.upper().replace(" ", "_")[:30]
        date_str = scheme.created_at.strftime("%Y_%m") if scheme.created_at else datetime.now().strftime("%Y_%m")
        return f"SCHEME_{scheme.id}_{name_clean}_{date_str}"
