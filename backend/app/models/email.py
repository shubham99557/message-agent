from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


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
    
    # Mandatory Human Approval Status
    approval_status = Column(String(50), default="draft")  # draft, approved, rejected, skipped, sent
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Sending Details
    sent_at = Column(DateTime, nullable=True)
    provider = Column(String(50), default="smtp")  # smtp, gmail, mock
    provider_message_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    campaign = relationship("Campaign", back_populates="email_drafts")
    company = relationship("Company", back_populates="email_drafts")
    contact = relationship("CompanyContact")
    approved_by = relationship("User")
    events = relationship("EmailEvent", back_populates="email_draft", cascade="all, delete-orphan")


class EmailEvent(Base):
    __tablename__ = "email_events"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("email_drafts.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)  # queued, sent, delivered, opened, clicked, bounced, complaint
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    details = Column(Text, nullable=True)  # JSON or message details

    email_draft = relationship("EmailDraft", back_populates="events")
