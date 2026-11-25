from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, ConfigDict


class EmailGenerateRequest(BaseModel):
    company_id: int
    contact_id: Optional[int] = None
    campaign_id: Optional[int] = None
    tone: str = "Friendly professional"  # Professional, Friendly professional, Friendly, Consultative, Technical, Formal, Short introductory, Follow-up
    draft_type: Optional[str] = "initial_email"  # initial_email, followup_email, short_intro, whatsapp_draft, linkedin_message
    variation_type: Optional[str] = "standard"  # short, standard, consultative
    service_id: Optional[int] = None
    custom_notes: Optional[str] = None


class EmailVariationItem(BaseModel):
    variation_type: str  # short, standard, consultative
    label: str           # Short Professional Introduction, Standard Personalized Business Email, Detailed Consultative Email
    subject: str
    body_text: str
    body_html: str
    tone: str
    description: str


class EmailVariationsRequest(BaseModel):
    company_id: int
    contact_id: Optional[int] = None
    tone: Optional[str] = "Professional"  # Professional, Friendly, Consultative, Technical
    service_id: Optional[int] = None
    custom_notes: Optional[str] = None


class EmailVariationsResponse(BaseModel):
    company_id: int
    company_name: str
    website: Optional[str] = None
    city: str
    industry: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    recipient_role: Optional[str] = None
    recipient_phone: Optional[str] = None
    matched_service_code: Optional[str] = None
    matched_service_name: Optional[str] = None
    service_match_reason: Optional[str] = None
    service_match_evidence: Optional[str] = None
    service_match_confidence: float = 0.0
    unsupported_assumptions: List[str] = []
    missing_information: List[str] = []
    source_evidence: List[Dict[str, Any]] = []
    subject_suggestions: List[str] = []
    variations: List[EmailVariationItem] = []
    generation_model: str = "llama3.2:latest"
    is_synthetic: bool = False


class EmailDraftUpdate(BaseModel):
    recipient_email: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    approval_status: Optional[str] = None  # draft, approved, rejected, skipped
    rejection_reason: Optional[str] = None
    scheduled_at: Optional[datetime] = None


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
    recipient_email: Optional[str] = None
    recipient_name: Optional[str] = None
    subject: str
    body_html: str
    body_text: str
    tone: str
    version: int = 1
    approval_status: str
    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    sent_at: Optional[datetime] = None
    provider: str
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    events: List[EmailEventResponse] = []
    
    # Enrichment fields for Approval & Outreach Dashboard
    company_name: Optional[str] = None
    company_city: Optional[str] = None
    contact_source_url: Optional[str] = None
    consent_status: Optional[str] = "unconsented"
    campaign_name: Optional[str] = None

    # Phase 3 AI Generation Provenance
    generation_model: Optional[str] = "llama3.2:latest"
    matched_service_code: Optional[str] = None
    matched_service_name: Optional[str] = None
    variation_type: Optional[str] = "standard"
    subject_suggestions: Optional[List[str]] = None
    source_evidence: Optional[str] = None
    missing_information: Optional[List[str]] = None

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
