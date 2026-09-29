import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base

class GovernmentScheme(Base):
    __tablename__ = "government_schemes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    scheme_name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    state = Column(String(100), default="All India", nullable=False) # e.g. Tamil Nadu or All India
    district = Column(String(100), default="All", nullable=True)
    eligible_crop = Column(String(100), default="All", nullable=True) # e.g. Tomato, Paddy, or All
    farmer_category = Column(String(100), default="All", nullable=True) # Small, Marginal, All
    eligibility_criteria = Column(Text, nullable=False)
    benefit = Column(Text, nullable=False)
    start_date = Column(String(50), nullable=True)
    deadline = Column(String(50), nullable=True)
    official_url = Column(String(255), nullable=False)

    # Verification flow
    verification_status = Column(String(50), default="PENDING_VERIFICATION", nullable=False) # PENDING_VERIFICATION, VERIFIED, PUBLISHED
    verified_by = Column(String(100), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
