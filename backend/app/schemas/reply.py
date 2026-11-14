from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class InboundReplyCreate(BaseModel):
    channel: str = "email"
    sender_identifier: str
    recipient_identifier: str = "outreach@acttrident.ai"
    subject: Optional[str] = None
    message_body: str


class ReplyResponse(BaseModel):
    id: int
    conversation_id: Optional[int] = None
    company_id: int
    channel: str
    sender_identifier: str
    recipient_identifier: str
    subject: Optional[str] = None
    message_body: str
    classification: str
    classification_confidence: float
    classification_reason: Optional[str] = None
    suggested_response: Optional[str] = None
    is_negotiation: bool
    human_approved: bool
    is_handled: bool
    received_at: datetime
    company_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class SuggestedResponseApproval(BaseModel):
    approved_text: Optional[str] = None
    send_immediately: bool = False
