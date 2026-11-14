from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


class WhatsAppTemplate(Base):
    __tablename__ = "whatsapp_templates"

    id = Column(Integer, primary_key=True, index=True)
    meta_template_name = Column(String(255), unique=True, nullable=False)
    category = Column(String(50), default="UTILITY")  # UTILITY, MARKETING
    language = Column(String(10), default="en")
    status = Column(String(50), default="APPROVED")  # APPROVED, PENDING, REJECTED
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
    
    # Consent Verification Check
    has_valid_consent = Column(Boolean, default=False)
    click_to_chat_url = Column(String(512), nullable=True)
    
    # Human Approval & Meta Delivery Status
    approval_status = Column(String(50), default="draft")  # draft, approved, rejected, sent
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    meta_message_id = Column(String(255), nullable=True)
    delivery_status = Column(String(50), default="draft")  # draft, queued, sent, delivered, read, failed
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
