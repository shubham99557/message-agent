from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict


class EmailGenerateRequest(BaseModel):
    company_id: int
    contact_id: Optional[int] = None
    campaign_id: Optional[int] = None
    tone: str = "Friendly professional"  # Formal, Friendly professional, Technical, Short introductory, Follow-up
    custom_notes: Optional[str] = None


class EmailDraftUpdate(BaseModel):
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    approval_status: Optional[str] = None  # draft, approved, rejected, skipped
    rejection_reason: Optional[str] = None


class EmailEventResponse(BaseModel):
    id: int
    event_type: str
    timestamp: datetime
    details: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class EmailDraftResponse(BaseModel):
    id: int
    campaign_id: Optional[int] = None
    company_id: int
    contact_id: Optional[int] = None
    recipient_email: str
    recipient_name: Optional[str] = None
    subject: str
    body_html: str
    body_text: str
    tone: str
    approval_status: str
    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    sent_at: Optional[datetime] = None
    provider: str
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    events: List[EmailEventResponse] = []
    
    # Enrichment fields for Approval Dashboard
    company_name: Optional[str] = None
    company_city: Optional[str] = None
    contact_source_url: Optional[str] = None
    consent_status: Optional[str] = "unconsented"
    campaign_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BulkApprovalRequest(BaseModel):
    draft_ids: List[int]
    action: str  # approve, reject, skip
    reason: Optional[str] = None


class EmailSendResult(BaseModel):
    draft_id: int
    status: str  # sent, failed, queued, blocked_suppression
    provider: str
    message: str
