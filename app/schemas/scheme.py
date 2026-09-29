from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class GovernmentSchemeCreate(BaseModel):
    scheme_name: str = Field(...)
    description: str = Field(...)
    state: str = Field(default="All India")
    district: Optional[str] = Field(default="All")
    eligible_crop: Optional[str] = Field(default="All")
    farmer_category: Optional[str] = Field(default="All")
    eligibility_criteria: str = Field(...)
    benefit: str = Field(...)
    start_date: Optional[str] = None
    deadline: Optional[str] = None
    official_url: str = Field(...)

class GovernmentSchemeVerify(BaseModel):
    action: str = Field(..., description="VERIFY or PUBLISH or REJECT")
    verified_by: str = Field(default="Admin")

class GovernmentSchemeResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    scheme_name: str
    description: str
    state: str
    district: Optional[str]
    eligible_crop: Optional[str]
    farmer_category: Optional[str]
    eligibility_criteria: str
    benefit: str
    start_date: Optional[str]
    deadline: Optional[str]
    official_url: str
    verification_status: str
    verified_by: Optional[str]
    verified_at: Optional[datetime]
    created_at: datetime
