from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CallJobCreate(BaseModel):
    farmer_id: int
    alert_id: Optional[int] = None
    event_id: str
    phone_number: str
    language: str = "ta-IN"
    priority: str = "NORMAL" # CRITICAL, HIGH, NORMAL, LOW
    max_retries: int = 3

class CallJobResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    job_id: str
    farmer_id: int
    alert_id: Optional[int]
    event_id: str
    phone_number: str
    language: str
    priority: str
    status: str
    attempts: int
    max_retries: int
    scheduled_for: datetime
    created_at: datetime


class CallLogResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    call_id: str
    job_id: Optional[str]
    farmer_id: int
    alert_id: Optional[int]
    event_id: str
    phone_number: str
    masked_phone: str
    language: str
    call_type: str
    provider: str
    provider_call_id: Optional[str]
    attempt_number: int
    status: str
    duration: int
    dtmf_response: Optional[str]
    opted_out: bool
    transcript_text: Optional[str]
    audio_url: Optional[str]
    failure_reason: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

class WebhookCallEvent(BaseModel):
    call_id: Optional[str] = None
    provider_call_id: Optional[str] = None
    event: str # CALL_STARTED, RINGING, ANSWERED, COMPLETED, BUSY, NO_ANSWER, FAILED, DTMF
    status: Optional[str] = None
    duration: Optional[int] = 0
    digits: Optional[str] = None # DTMF input (1, 2, 9, 0)
    failure_reason: Optional[str] = None
