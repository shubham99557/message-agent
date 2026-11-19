from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


EMAIL_STATES = [
    "draft",
    "awaiting_approval",
    "approved",
    "queued",
    "sending",
    "sent",
    "delivered",
    "bounced",
    "failed",
    "rejected",
    "skipped",
    "cancelled",
    "simulated"
]


class EmailDraft(Base):
    __tablename__ = "email_drafts"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(Integer, ForeignKey("company_contacts.id", ondelete="SET NULL"), nullable=True)
    
    recipient_email = Column(String(255), nullable=False)
    recipient_name = Column(String(255), nullable=True)
    subject = Column(String(512), nullable=False)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text, nullable=False)
    tone = Column(String(50), default="Friendly professional")  # Formal, Friendly professional, Technical, Short introductory, Follow-up
    
    # Versioning & Immutability Content Hash
    version = Column(Integer, default=1, nullable=False)
    content_hash = Column(String(64), nullable=True)  # SHA-256 of subject + body_text
    approved_content_hash = Column(String(64), nullable=True)  # Set strictly upon human approval

    # Mandatory Human Approval Status
    approval_status = Column(String(50), default="draft", index=True)  # draft, awaiting_approval, approved, queued, sending, sent, delivered, bounced, failed, rejected, skipped, cancelled, simulated
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Sending Details
    sent_at = Column(DateTime, nullable=True)
    provider = Column(String(50), default="smtp")  # smtp, gmail, mock
    provider_message_id = Column(String(255), nullable=True, index=True)
    provider_thread_id = Column(String(255), nullable=True, index=True)
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    campaign = relationship("Campaign", back_populates="email_drafts")
    company = relationship("Company", back_populates="email_drafts")
    contact = relationship("CompanyContact")
    approved_by = relationship("User")
    events = relationship("EmailEvent", back_populates="email_draft", cascade="all, delete-orphan")
    send_attempts = relationship("EmailSendAttempt", back_populates="email_draft", cascade="all, delete-orphan")


class EmailEvent(Base):
    __tablename__ = "email_events"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("email_drafts.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)  # queued, sent, delivered, opened, clicked, bounced, complaint
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    details = Column(Text, nullable=True)  # JSON or message details

    email_draft = relationship("EmailDraft", back_populates="events")


class ApprovalRecord(Base):
    """Immutable ledger of every approval, rejection, skip, and post-edit invalidation."""
    __tablename__ = "approval_records"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False, index=True)  # email_draft, whatsapp_message, linkedin_message
    entity_id = Column(Integer, nullable=False, index=True)
    approver_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)  # approved, rejected, skipped, invalidated_by_edit
    content_version = Column(Integer, default=1, nullable=False)
    content_hash = Column(String(64), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    approver = relationship("User")


class EmailSendAttempt(Base):
    """Records every discrete outbound send attempt separately from delivery outcomes."""
    __tablename__ = "email_send_attempts"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("email_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number = Column(Integer, default=1, nullable=False)
    idempotency_key = Column(String(128), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # gmail, smtp, mock
    outcome = Column(String(50), nullable=False, index=True)  # sent, smtp_accepted, simulated, failed, reauth_required, rate_limited
    provider_message_id = Column(String(255), nullable=True)
    provider_thread_id = Column(String(255), nullable=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    attempted_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    email_draft = relationship("EmailDraft", back_populates="send_attempts")
    attempted_by = relationship("User")
