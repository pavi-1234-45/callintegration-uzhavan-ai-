from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AlertCreate(BaseModel):
    alert_type: str = Field(..., description="WEATHER, MARKET, SCHEME, NEWS")
    event_id: str = Field(..., description="Stable deterministic event id")
    title: str = Field(...)
    severity: str = Field(default="NORMAL", description="CRITICAL, HIGH, NORMAL, LOW")
    state: Optional[str] = None
    district: Optional[str] = None
    crop: Optional[str] = None
    summary_text: str = Field(...)
    content_json: Optional[str] = None

class AlertResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    alert_id: str
    event_id: str
    alert_type: str
    title: str
    severity: str
    state: Optional[str]
    district: Optional[str]
    crop: Optional[str]
    summary_text: str
    content_json: Optional[str]
    is_active: bool
    created_at: datetime
