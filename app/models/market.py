import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.database import Base

class MarketPriceUpdate(Base):
    __tablename__ = "market_price_updates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    commodity = Column(String(100), nullable=False, index=True)
    variety = Column(String(100), nullable=True)
    state = Column(String(100), default="Tamil Nadu")
    market = Column(String(150), nullable=False)
    modal_price = Column(Float, nullable=False)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    unit = Column(String(50), default="Quintal")
    trend = Column(String(50), default="stable") # rising, falling, stable
    percentage_change = Column(Float, default=0.0)
    source = Column(String(150), default="Agmarknet (Govt of India)")
    arrival_date = Column(String(50), nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
