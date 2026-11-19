from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Index
from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(255), nullable=False)  # login, approve_email, reject_email, send_email, update_crm, opt_out, etc.
    entity_type = Column(String(100), nullable=False)  # email_draft, company, lead, consent, campaign
    entity_id = Column(String(100), nullable=True)
    ip_address = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)  # JSON formatted extra data
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class SuppressionList(Base):
    __tablename__ = "suppression_list"
    __table_args__ = (
        Index("ix_suppression_identifier_channel", "identifier", "channel"),
    )

    id = Column(Integer, primary_key=True, index=True)
    identifier = Column(String(255), unique=True, index=True, nullable=False)  # email address or phone number
    channel = Column(String(50), default="all")  # email, whatsapp, all
    reason = Column(String(255), default="user_opt_out")  # unsubscribe, user_opt_out, explicit_refusal, bounce_complaint
    source = Column(String(255), default="inbound_reply")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class IntegrationCredential(Base):
    __tablename__ = "integration_credentials"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(100), unique=True, nullable=False)  # gemini, openai, smtp, gmail, whatsapp_meta, mautic, chatwoot
    key_identifier = Column(String(255), nullable=True)
    encrypted_value = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
