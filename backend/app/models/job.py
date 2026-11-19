from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base

TASK_CATEGORIES = [
    "company_discovery",
    "company_enrichment",
    "website_research",
    "lead_qualification",
    "email_generation",
    "whatsapp_generation",
    "email_dispatch",
    "whatsapp_dispatch",
    "reply_ingestion",
    "reply_classification",
    "crm_update",
    "followup_scheduling",
    "daily_reporting",
    "outbox_dispatch",
    "gmail_reply_sync"
]

TASK_STATUSES = [
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
    "retrying",
    "dead_letter"
]


class BackgroundTaskRecord(Base):
    __tablename__ = "background_task_records"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(255), unique=True, index=True, nullable=False)
    category = Column(String(100), index=True, nullable=False)
    idempotency_key = Column(String(128), unique=True, index=True, nullable=True)
    status = Column(String(50), default="pending", index=True, nullable=False)
    
    payload_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    campaign = relationship("Campaign")
    company = relationship("Company")


class DeadLetterTask(Base):
    __tablename__ = "dead_letter_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(255), index=True, nullable=False)
    category = Column(String(100), index=True, nullable=False)
    idempotency_key = Column(String(128), nullable=True)
    payload_json = Column(Text, nullable=True)
    final_error = Column(Text, nullable=False)
    retries_exhausted = Column(Integer, default=3, nullable=False)
    failed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    requeued = Column(Boolean, default=False, nullable=False)
