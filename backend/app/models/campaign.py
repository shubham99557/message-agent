from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    objective = Column(Text, nullable=False)
    target_city = Column(String(100), nullable=True)  # Siliguri, Gangtok, Patna, Bhagalpur, All
    target_industry = Column(String(255), nullable=True)
    status = Column(String(50), default="draft")  # draft, scheduled, active, paused, completed
    
    # Conservative Limits & Schedules
    daily_email_limit = Column(Integer, default=50)
    daily_whatsapp_limit = Column(Integer, default=20)
    sending_schedule = Column(String(100), default="09:00-18:00 IST Weekdays")
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    recipients = relationship("CampaignRecipient", back_populates="campaign", cascade="all, delete-orphan")
    email_drafts = relationship("EmailDraft", back_populates="campaign", cascade="all, delete-orphan")
    whatsapp_messages = relationship("WhatsAppMessage", back_populates="campaign", cascade="all, delete-orphan")


class CampaignRecipient(Base):
    __tablename__ = "campaign_recipients"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(Integer, ForeignKey("company_contacts.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="pending")  # pending, email_drafted, email_approved, email_sent, wa_sent, replied, bounced, opted_out
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    campaign = relationship("Campaign", back_populates="recipients")
    company = relationship("Company", back_populates="campaign_recipients")
    contact = relationship("CompanyContact")
