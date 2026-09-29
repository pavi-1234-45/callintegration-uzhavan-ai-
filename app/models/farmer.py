import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Farmer(Base):
    __tablename__ = "farmers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    farmer_id = Column(String(50), unique=True, index=True, nullable=False) # e.g. UZH-FARM-00101
    name = Column(String(150), nullable=False, index=True)
    phone = Column(String(20), nullable=False, index=True) # Full phone number
    preferred_language = Column(String(10), default="ta-IN", nullable=False) # ta-IN, en-IN, te-IN, kn-IN, ml-IN, hi-IN
    farmer_category = Column(String(50), default="Small", nullable=True) # Small, Marginal, Medium, Large

    # Location Details
    state = Column(String(100), nullable=False, default="Tamil Nadu")
    district = Column(String(100), nullable=False, index=True)
    taluk = Column(String(100), nullable=True)
    village = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Crop Details
    main_crop = Column(String(100), nullable=False, index=True)
    additional_crops = Column(String(255), nullable=True)
    crop_season = Column(String(50), default="Rabi")

    # Consent, Voice Preferences and Source Identification
    consent_given = Column(Boolean, default=False, nullable=False)
    consent_timestamp = Column(DateTime, nullable=True)
    voice_alerts_enabled = Column(Boolean, default=False, nullable=False)
    source = Column(String(50), default="survey_portal", nullable=False) # 'mobile_app', 'survey_portal'

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    call_jobs = relationship("CallJob", back_populates="farmer", cascade="all, delete-orphan")
    call_logs = relationship("CallLog", back_populates="farmer", cascade="all, delete-orphan")

    @property
    def masked_phone(self) -> str:
        """Returns phone number with middle digits masked: e.g. +91 98****3210"""
        p = self.phone or ""
        if len(p) >= 10:
            return p[:4] + "****" + p[-4:]
        elif len(p) >= 4:
            return "****" + p[-4:]
        return "****"

# Alias for VoiceRegisteredFarmer
VoiceRegisteredFarmer = Farmer
