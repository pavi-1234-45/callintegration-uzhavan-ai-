import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class CallJob(Base):
    __tablename__ = "call_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String(50), unique=True, index=True, nullable=False) # e.g. JOB-20260927-0012
    farmer_id = Column(Integer, ForeignKey("farmers.id"), nullable=False, index=True)
    alert_id = Column(Integer, ForeignKey("agricultural_alerts.id"), nullable=True, index=True)
    event_id = Column(String(100), index=True, nullable=False) # Deterministic event hash/id for deduplication
    
    phone_number = Column(String(20), nullable=False)
    language = Column(String(10), default="ta-IN", nullable=False)
    priority = Column(String(20), default="NORMAL", nullable=False) # CRITICAL, HIGH, NORMAL, LOW
    status = Column(String(30), default="QUEUED", index=True, nullable=False) # QUEUED, IN_PROGRESS, COMPLETED, FAILED, RETRY_PENDING, CANCELLED

    attempts = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    next_retry_at = Column(DateTime, nullable=True)
    scheduled_for = Column(DateTime, default=datetime.datetime.utcnow)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    farmer = relationship("Farmer", back_populates="call_jobs")
    alert = relationship("AgriculturalAlert", backref="call_jobs")


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    call_id = Column(String(50), unique=True, index=True, nullable=False) # e.g. CALL-20260927-0012
    job_id = Column(String(50), index=True, nullable=True)
    farmer_id = Column(Integer, ForeignKey("farmers.id"), nullable=False, index=True)
    alert_id = Column(Integer, ForeignKey("agricultural_alerts.id"), nullable=True, index=True)
    event_id = Column(String(100), index=True, nullable=False)

    phone_number = Column(String(20), nullable=False)
    language = Column(String(10), default="ta-IN", nullable=False)
    call_type = Column(String(50), default="WEATHER", nullable=False) # WEATHER, MARKET, SCHEME, NEWS, MANUAL
    provider = Column(String(50), default="SIMULATION", nullable=False) # EXOTEL, TWILIO, SIMULATION
    provider_call_id = Column(String(100), index=True, nullable=True)

    attempt_number = Column(Integer, default=1, nullable=False)
    status = Column(String(30), default="CALL_STARTED", index=True, nullable=False) # CALL_STARTED, RINGING, ANSWERED, COMPLETED, BUSY, NO_ANSWER, FAILED
    duration = Column(Integer, default=0) # Duration in seconds
    dtmf_response = Column(String(10), nullable=True) # DTMF: 1=Repeat, 2=More, 9=End, 0=OptOut
    opted_out = Column(Boolean, default=False)

    transcript_text = Column(Text, nullable=True)
    audio_url = Column(String(500), nullable=True)
    failure_reason = Column(String(255), nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    farmer = relationship("Farmer", back_populates="call_logs")
    alert = relationship("AgriculturalAlert", backref="call_logs")

    @property
    def masked_phone(self) -> str:
        p = self.phone_number or ""
        if len(p) >= 10:
            return p[:4] + "****" + p[-4:]
        elif len(p) >= 4:
            return "****" + p[-4:]
        return "****"
