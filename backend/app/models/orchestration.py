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


class SchedulerJobRecord(Base):
    """
    Durable persistence of background scheduler job execution state.
    Tracks last run, last success, next due, and total run count across application restarts.
    """
    __tablename__ = "scheduler_job_records"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(100), unique=True, nullable=False, index=True)
    last_run_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_status = Column(String(50), nullable=True)  # success, failed, blocked, skipped, executed
    last_error = Column(Text, nullable=True)
    total_runs = Column(Integer, default=0, nullable=False)
    interval_seconds = Column(Integer, default=60, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class SchedulerExecutionHistory(Base):
    """
    Audit log of scheduler job runs persisted to SQLite.
    """
    __tablename__ = "scheduler_execution_history"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True)  # success, failed, blocked, skipped, executed
    detail = Column(Text, nullable=True)
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
