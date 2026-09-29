from pydantic import BaseModel, Field, field_validator
import re
from typing import Optional
from datetime import datetime

class FarmerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, description="Farmer Full Name")
    phone: str = Field(..., min_length=10, max_length=15, description="Mobile Phone Number")
    preferred_language: str = Field(default="ta-IN", description="Preferred Language Code (ta-IN, en-IN, te-IN, kn-IN, ml-IN, hi-IN)")
    farmer_category: Optional[str] = Field(default="Small", description="Farmer Category: Small, Marginal, Medium, Large")

    # Location
    state: str = Field(default="Tamil Nadu", description="State")
    district: str = Field(..., min_length=2, description="District")
    taluk: Optional[str] = Field(default=None, description="Taluk / Sub-district")
    village: Optional[str] = Field(default=None, description="Village / Gram Panchayat")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="GPS Latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="GPS Longitude")

    # Crops
    main_crop: str = Field(..., min_length=2, description="Main Crop (e.g. Tomato, Paddy, Onion)")
    additional_crops: Optional[str] = Field(default="", description="Additional Crops (comma separated)")
    crop_season: Optional[str] = Field(default="Rabi", description="Crop Season: Kharif, Rabi, Zaid, Annual")

    # Voice Consent
    consent_given: bool = Field(..., description="Consent to receive automated agricultural voice calls")
    voice_alerts_enabled: bool = Field(default=True, description="Enable Voice Alerts immediately")
    source: Optional[str] = Field(default="survey_portal", description="Source: mobile_app or survey_portal")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[^\d+]", "", v)
        digits_only = re.sub(r"[^\d]", "", cleaned)
        if len(digits_only) < 10:
            raise ValueError("Phone number must contain at least 10 valid digits.")
        # Standardize Indian phone number format
        if len(digits_only) == 10:
            return f"+91{digits_only}"
        elif len(digits_only) == 12 and digits_only.startswith("91"):
            return f"+{digits_only}"
        return cleaned

    @field_validator("preferred_language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        valid_languages = ["ta-IN", "en-IN", "te-IN", "kn-IN", "ml-IN", "hi-IN"]
        if v not in valid_languages:
            raise ValueError(f"Language must be one of {valid_languages}")
        return v

class FarmerUpdate(BaseModel):
    name: Optional[str] = None
    preferred_language: Optional[str] = None
    farmer_category: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    taluk: Optional[str] = None
    village: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    main_crop: Optional[str] = None
    additional_crops: Optional[str] = None
    crop_season: Optional[str] = None
    consent_given: Optional[bool] = None
    voice_alerts_enabled: Optional[bool] = None
    source: Optional[str] = None

class FarmerResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    farmer_id: str
    name: str
    phone: str
    masked_phone: str
    preferred_language: str
    farmer_category: Optional[str]
    state: str
    district: str
    taluk: Optional[str]
    village: Optional[str]
    latitude: float
    longitude: float
    main_crop: str
    additional_crops: Optional[str]
    crop_season: Optional[str]
    consent_given: bool
    voice_alerts_enabled: bool
    source: str = "survey_portal"
    created_at: datetime

class FarmerRegistrationConfirmation(BaseModel):
    success: bool
    message: str
    farmer_id: str
    name: str
    masked_phone: str
    location: str
    crop: str
    language: str
    voice_alerts: str
    registered_at: datetime
