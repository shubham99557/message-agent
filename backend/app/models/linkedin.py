from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


LINKEDIN_MESSAGE_TYPES = [
    "connection_note",
    "direct_message",
    "inmail_draft",
    "follow_up",
]

LINKEDIN_MESSAGE_STATES = [
    "draft",
    "approved",
    "rejected",
    "ready_for_manual_send",
    "manually_sent_confirmed",
    "sending",
    "sent_via_api",
    "failed",
]


class LinkedInMessage(Base):
    """
    Compliant LinkedIn outreach message record.
    Supports mandatory human approval, content-hash integrity, and either:
    - 'manual_handoff': compliant human-assisted copy & send inside LinkedIn (default for standard OAuth apps)
    - 'authorized_partner_api': official LinkedIn Partner API dispatch when explicitly approved and configured
    Never uses browser-cookie extraction, password collection, or unauthorized scraping.
    """
    __tablename__ = "linkedin_messages"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)

    recipient_name = Column(String(255), nullable=True)
    recipient_profile_url = Column(String(500), nullable=False)
    message_type = Column(String(50), default="connection_note", nullable=False)  # connection_note, direct_message, inmail_draft, follow_up
    tone = Column(String(100), default="Consultative", nullable=False)
    message_body = Column(Text, nullable=False)

    # Tamper-evident hash of (recipient_profile_url | message_type | message_body)
    content_hash = Column(String(64), nullable=False, index=True)
    approval_status = Column(String(50), default="draft", nullable=False, index=True)
    rejection_reason = Column(Text, nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Honest delivery tracking
    delivery_mode = Column(String(50), default="manual_handoff", nullable=False)  # manual_handoff, authorized_partner_api
    provider_message_id = Column(String(255), nullable=True, index=True)  # NULL unless returned by authorized API
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    sent_at = Column(DateTime, nullable=True)
    sent_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    failure_reason = Column(Text, nullable=True)

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    company = relationship("Company")
