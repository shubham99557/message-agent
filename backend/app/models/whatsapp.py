from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


class WhatsAppTemplate(Base):
    __tablename__ = "whatsapp_templates"

    id = Column(Integer, primary_key=True, index=True)
    meta_template_id = Column(String(255), nullable=True, index=True)
    meta_template_name = Column(String(255), unique=True, nullable=False)
    category = Column(String(50), default="UTILITY")  # UTILITY, MARKETING, AUTHENTICATION
    language = Column(String(20), default="en")
    status = Column(String(50), default="PENDING")  # APPROVED, PENDING, REJECTED, PAUSED, DISABLED (synced from Meta)
    synced_from_meta = Column(Boolean, default=False, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    header_text = Column(String(255), nullable=True)
    body_text = Column(Text, nullable=False)
    footer_text = Column(String(255), nullable=True)
    variables_schema = Column(Text, nullable=True)  # JSON schema of parameters
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    messages = relationship("WhatsAppMessage", back_populates="template")


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(Integer, ForeignKey("company_contacts.id", ondelete="SET NULL"), nullable=True)
    template_id = Column(Integer, ForeignKey("whatsapp_templates.id", ondelete="SET NULL"), nullable=True)
    consent_id = Column(Integer, ForeignKey("contact_consent.id", ondelete="SET NULL"), nullable=True)
    
    recipient_phone = Column(String(100), nullable=False)
    message_text = Column(Text, nullable=False)
    parameters_json = Column(Text, nullable=True)
    
    # Versioning & Content Immutability
    version = Column(Integer, default=1, nullable=False)
    content_hash = Column(String(64), nullable=True)
    approved_content_hash = Column(String(64), nullable=True)

    # Consent Verification Check
    has_valid_consent = Column(Boolean, default=False)
    click_to_chat_url = Column(String(512), nullable=True)
    
    # Human Approval & Meta Delivery Status
    approval_status = Column(String(50), default="draft")  # draft, approved, rejected, sent, simulated
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    meta_message_id = Column(String(255), nullable=True, index=True)
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    delivery_status = Column(String(50), default="draft")  # draft, queued, sending, sent, delivered, read, failed, simulated
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    campaign = relationship("Campaign", back_populates="whatsapp_messages")
    company = relationship("Company", back_populates="whatsapp_messages")
    contact = relationship("CompanyContact")
    template = relationship("WhatsAppTemplate", back_populates="messages")
    consent = relationship("ContactConsent")
    approved_by = relationship("User")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, index=True)  # meta_whatsapp, gmail, sendgrid
    event_id = Column(String(255), nullable=True, index=True)
    idempotency_key = Column(String(128), unique=True, index=True, nullable=False)
    payload_json = Column(Text, nullable=False)
    status = Column(String(50), default="received")  # received, processed, ignored, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)
