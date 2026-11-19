from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


OUTBOX_STATUSES = [
    "pending",
    "processing",
    "dispatched",
    "failed",
    "cancelled",
]


class SystemSetting(Base):
    """
    Persistent operational control flags (e.g. Global Emergency Kill Switch,
    IST business-hours boundaries) stored durably in the database.
    """
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(120), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    updated_by = relationship("User")


class OutboundDispatchOutbox(Base):
    """
    Durable transactional outbox guaranteeing crash-safe, idempotent, exactly-once
    outbound dispatch across Email, WhatsApp, and Authorized LinkedIn channels.
    """
    __tablename__ = "outbound_dispatch_outbox"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String(50), nullable=False, index=True)  # email, whatsapp, linkedin
    entity_id = Column(Integer, nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    idempotency_key = Column(String(160), unique=True, nullable=False, index=True)

    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, processing, dispatched, failed, cancelled
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    next_retry_at = Column(DateTime, nullable=True, index=True)
    last_error = Column(Text, nullable=True)
    result_summary = Column(Text, nullable=True)

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime, nullable=True)

    campaign = relationship("Campaign")
    created_by = relationship("User")
