import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from app.database import Base

class AgriculturalAlert(Base):
    __tablename__ = "agricultural_alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    alert_id = Column(String(50), unique=True, index=True, nullable=False) # e.g. UZH-ALT-20260927-001
    event_id = Column(String(100), index=True, nullable=False) # e.g. MADURAI_HEAVY_RAIN_2026_09_27
    alert_type = Column(String(50), nullable=False, index=True) # WEATHER, MARKET, SCHEME, NEWS
    title = Column(String(255), nullable=False)
    severity = Column(String(20), default="NORMAL", nullable=False) # CRITICAL, HIGH, NORMAL, LOW

    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True, index=True)
    crop = Column(String(100), nullable=True, index=True)

    summary_text = Column(Text, nullable=False)
    content_json = Column(Text, nullable=True) # JSON representation of raw alert data
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
