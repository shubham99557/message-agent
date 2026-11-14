from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.schemas.company import CompanyResponse


class LeadBase(BaseModel):
    pipeline_status: str = "new"
    last_contact_date: Optional[datetime] = None
    next_followup_date: Optional[datetime] = None
    meeting_notes: Optional[str] = None
    product_feedback: Optional[str] = None
    trial_status: str = "none"
    trial_start_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    trial_device_count: Optional[int] = None
    conversion_value: float = 0.0
    assigned_user_id: Optional[int] = None


class LeadUpdate(BaseModel):
    pipeline_status: Optional[str] = None
    last_contact_date: Optional[datetime] = None
    next_followup_date: Optional[datetime] = None
    meeting_notes: Optional[str] = None
    product_feedback: Optional[str] = None
    trial_status: Optional[str] = None
    trial_start_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    trial_device_count: Optional[int] = None
    conversion_value: Optional[float] = None
    assigned_user_id: Optional[int] = None


class FollowupCreate(BaseModel):
    scheduled_date: datetime
    suggested_channel: str = "email"
    notes: Optional[str] = None


class FollowupResponse(FollowupCreate):
    id: int
    lead_id: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MeetingCreate(BaseModel):
    title: str
    scheduled_at: datetime
    duration_minutes: int = 30
    meeting_url: Optional[str] = None
    notes: Optional[str] = None


class MeetingResponse(MeetingCreate):
    id: int
    lead_id: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TrialCreate(BaseModel):
    program_name: str = "ActTrident 90-Day Free Evaluation"
    start_date: datetime
    end_date: datetime
    devices_count: int = 5
    status: str = "active"
    feedback: Optional[str] = None


class TrialResponse(TrialCreate):
    id: int
    lead_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LeadResponse(LeadBase):
    id: int
    company_id: int
    followup_count: int
    created_at: datetime
    updated_at: datetime
    company: Optional[CompanyResponse] = None
    meetings: List[MeetingResponse] = []
    followups: List[FollowupResponse] = []
    trials: List[TrialResponse] = []
    model_config = ConfigDict(from_attributes=True)
