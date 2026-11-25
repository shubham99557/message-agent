from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class LinkedInDraftCreate(BaseModel):
    company_id: int
    campaign_id: Optional[int] = None
    recipient_name: Optional[str] = None
    recipient_profile_url: Optional[str] = None
    message_type: str = Field(default="connection_note")  # connection_note, direct_message, inmail_draft, follow_up
    tone: str = Field(default="Consultative")
    custom_message: Optional[str] = None
    custom_notes: Optional[str] = None


class LinkedInDraftUpdate(BaseModel):
    recipient_name: Optional[str] = None
    recipient_profile_url: Optional[str] = None
    message_body: Optional[str] = None


class LinkedInRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class LinkedInManualSendConfirmRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=500)


class LinkedInMessageResponse(BaseModel):
    id: int
    company_id: int
    campaign_id: Optional[int] = None
    company_name: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_profile_url: str
    message_type: str
    tone: str
    message_body: str
    content_hash: str
    approval_status: str
    rejection_reason: Optional[str] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    delivery_mode: str
    provider_message_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
