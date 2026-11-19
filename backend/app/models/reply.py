from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from app.core.database import Base


REPLY_CATEGORIES = [
    "interested",
    "wants_more_information",
    "requests_demonstration",
    "requests_pricing",
    "not_interested",
    "wants_a_callback",
    "wrong_contact",
    "out_of_office",
    "unsubscribe",
    "potential_partnership"
]


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(Integer, ForeignKey("company_contacts.id", ondelete="SET NULL"), nullable=True)
    channel = Column(String(50), default="email")  # email, whatsapp
    subject = Column(String(512), nullable=True)
    last_message_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    replies = relationship("Reply", back_populates="conversation", cascade="all, delete-orphan")


class Reply(Base):
    __tablename__ = "replies"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(Integer, ForeignKey("company_contacts.id", ondelete="SET NULL"), nullable=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    
    channel = Column(String(50), default="email")  # email, whatsapp
    provider_message_id = Column(String(255), unique=True, nullable=True, index=True)
    provider_thread_id = Column(String(255), nullable=True, index=True)
    sender_identifier = Column(String(255), nullable=False)  # email address or phone number
    recipient_identifier = Column(String(255), nullable=False)
    subject = Column(String(512), nullable=True)
    message_body = Column(Text, nullable=False)
    
    # 10-Class AI Classification
    classification = Column(String(50), default="wants_more_information", index=True)
    classification_confidence = Column(Float, default=0.0)
    classification_reason = Column(Text, nullable=True)
    
    # Suggested AI Response & Human Approval Requirement
    suggested_response = Column(Text, nullable=True)
    is_negotiation = Column(Boolean, default=False)
    human_approved = Column(Boolean, default=False)
    is_handled = Column(Boolean, default=False)
    
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="replies")
    company = relationship("Company")
    contact = relationship("CompanyContact")
