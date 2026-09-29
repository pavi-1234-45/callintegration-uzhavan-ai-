import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base

class AgriculturalNews(Base):
    __tablename__ = "agricultural_news"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(300), nullable=False)
    summary = Column(Text, nullable=False)
    source = Column(String(100), nullable=False) # thehindu, toi, pib, etc.
    tag = Column(String(50), default="general") # weather, scheme, market, advisory, pest
    state = Column(String(100), default="tamil_nadu")
    crop = Column(String(100), nullable=True) # crop specific if tagged
    relevance_score = Column(Integer, default=50) # 0 to 100 deterministic scoring
    image_url = Column(String(500), nullable=True)
    published_date = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
