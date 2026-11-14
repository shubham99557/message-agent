from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class CampaignBase(BaseModel):
    name: str
    objective: str
    target_city: Optional[str] = None
    target_industry: Optional[str] = None
    status: str = "draft"  # draft, scheduled, active, paused, completed
    daily_email_limit: int = 50
    daily_whatsapp_limit: int = 20
    sending_schedule: str = "09:00-18:00 IST Weekdays"


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    objective: Optional[str] = None
    target_city: Optional[str] = None
    target_industry: Optional[str] = None
    status: Optional[str] = None
    daily_email_limit: Optional[int] = None
    daily_whatsapp_limit: Optional[int] = None
    sending_schedule: Optional[str] = None


class CampaignRecipientResponse(BaseModel):
    id: int
    campaign_id: int
    company_id: int
    contact_id: Optional[int] = None
    status: str
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CampaignResponse(CampaignBase):
    id: int
    created_at: datetime
    updated_at: datetime
    recipients_count: int = 0
    emails_drafted: int = 0
    emails_approved: int = 0
    emails_sent: int = 0
    model_config = ConfigDict(from_attributes=True)
