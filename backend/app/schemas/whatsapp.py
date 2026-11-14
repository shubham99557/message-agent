from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class WhatsAppTemplateResponse(BaseModel):
    id: int
    meta_template_name: str
    category: str
    language: str
    status: str
    header_text: Optional[str] = None
    body_text: str
    footer_text: Optional[str] = None
    variables_schema: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ContactConsentCreate(BaseModel):
    company_id: int
    contact_id: Optional[int] = None
    channel: str = "whatsapp"
    consent_status: str  # opted_in, unconsented, opted_out
    consent_source: str  # e.g., "Web Form Inbound", "Business Card Handover", "Explicit Email Confirmation"
    consent_purpose: str = "ActTrident 90-day evaluation product inquiry"
    proof_reference: Optional[str] = None
    notes: Optional[str] = None


class ContactConsentResponse(ContactConsentCreate):
    id: int
    consent_date: Optional[datetime] = None
    opt_out_date: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WhatsAppDraftRequest(BaseModel):
    company_id: int
    contact_id: Optional[int] = None
    template_name: str
    parameters: Dict[str, str] = {}
    campaign_id: Optional[int] = None


class WhatsAppMessageResponse(BaseModel):
    id: int
    campaign_id: Optional[int] = None
    company_id: int
    contact_id: Optional[int] = None
    template_id: Optional[int] = None
    recipient_phone: str
    message_text: str
    has_valid_consent: bool
    click_to_chat_url: Optional[str] = None
    approval_status: str
    meta_message_id: Optional[str] = None
    delivery_status: str
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
