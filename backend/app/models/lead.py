from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


PIPELINE_STATUSES = [
    "new",
    "researching",
    "researched",
    "qualified",
    "unqualified",
    "draft_ready",
    "awaiting_approval",
    "approved",
    "queued",
    "sending",
    "provider_accepted",
    "contacted",
    "delivered",
    "replied",
    "interested",
    "not_interested",
    "meeting_scheduled",
    "demo_completed",
    "trial_offered",
    "trial_started",
    "trial_activated",
    "converted",
    "bounced",
    "failed",
    "opted_out",
    "lost",
    "do_not_contact"
]

PIPELINE_TRANSITIONS = {
    "new": ["researching", "researched", "qualified", "unqualified", "do_not_contact", "opted_out"],
    "researching": ["researched", "qualified", "unqualified", "do_not_contact", "opted_out"],
    "researched": ["qualified", "unqualified", "draft_ready", "awaiting_approval", "do_not_contact", "opted_out"],
    "qualified": ["draft_ready", "awaiting_approval", "unqualified", "do_not_contact", "opted_out"],
    "unqualified": ["qualified", "do_not_contact"],
    "draft_ready": ["awaiting_approval", "approved", "do_not_contact", "opted_out"],
    "awaiting_approval": ["approved", "rejected", "draft_ready", "do_not_contact", "opted_out"],
    "approved": ["queued", "sending", "provider_accepted", "contacted", "bounced", "failed", "do_not_contact", "opted_out"],
    "queued": ["sending", "provider_accepted", "contacted", "failed", "do_not_contact", "opted_out"],
    "sending": ["provider_accepted", "contacted", "delivered", "bounced", "failed", "opted_out"],
    "provider_accepted": ["delivered", "contacted", "replied", "bounced", "opted_out"],
    "contacted": ["delivered", "replied", "interested", "not_interested", "bounced", "opted_out", "do_not_contact"],
    "delivered": ["replied", "interested", "not_interested", "bounced", "opted_out", "do_not_contact"],
    "replied": ["interested", "not_interested", "meeting_scheduled", "opted_out", "do_not_contact"],
    "interested": ["meeting_scheduled", "demo_completed", "trial_offered", "trial_started", "opted_out", "do_not_contact"],
    "meeting_scheduled": ["demo_completed", "trial_offered", "trial_started", "not_interested", "do_not_contact"],
    "demo_completed": ["trial_offered", "trial_started", "converted", "lost", "do_not_contact"],
    "trial_offered": ["trial_started", "trial_activated", "lost", "do_not_contact"],
    "trial_started": ["trial_activated", "converted", "lost", "do_not_contact"],
    "trial_activated": ["converted", "lost", "do_not_contact"],
    "converted": [],
    "bounced": ["do_not_contact", "opted_out"],
    "failed": ["queued", "sending", "do_not_contact"],
    "opted_out": [],
    "lost": ["new", "researching"],
    "not_interested": ["do_not_contact", "opted_out"],
    "do_not_contact": []
}


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)
    pipeline_status = Column(String(50), default="new", index=True)
    
    # Activity & Followup tracking
    last_contact_date = Column(DateTime, nullable=True)
    next_followup_date = Column(DateTime, nullable=True)
    followup_count = Column(Integer, default=0)
    
    # Meeting & Evaluation notes
    notes = Column(Text, nullable=True)
    meeting_notes = Column(Text, nullable=True)
    product_feedback = Column(Text, nullable=True)
    
    # 90-day Evaluation Program tracking
    trial_status = Column(String(50), default="none")  # none, offered, active, completed, expired, declined
    trial_start_date = Column(DateTime, nullable=True)
    trial_end_date = Column(DateTime, nullable=True)
    trial_device_count = Column(Integer, nullable=True)
    
    # Conversion metrics
    conversion_value = Column(Float, default=0.0)
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="lead")
    assigned_user = relationship("User")
    meetings = relationship("Meeting", back_populates="lead", cascade="all, delete-orphan")
    followups = relationship("Followup", back_populates="lead", cascade="all, delete-orphan")
    trials = relationship("Trial", back_populates="lead", cascade="all, delete-orphan")


class Followup(Base):
    __tablename__ = "followups"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    scheduled_date = Column(DateTime, nullable=False, index=True)
    due_date = Column(DateTime, nullable=True, index=True)
    status = Column(String(50), default="not_contacted", nullable=False, index=True)  # not_contacted, draft_ready, awaiting_approval, approved, sent, replied, interested, not_interested, follow_up_due, converted, closed, pending, completed, cancelled
    suggested_channel = Column(String(50), default="email")  # email, call, whatsapp, meeting
    reminder_at = Column(DateTime, nullable=True, index=True)
    reason = Column(String(255), nullable=True)
    next_action = Column(String(255), nullable=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    lead = relationship("Lead", back_populates="followups")
    company = relationship("Company")
    assigned_user = relationship("User")


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=30)
    meeting_url = Column(String(512), nullable=True)
    status = Column(String(50), default="scheduled")  # scheduled, completed, cancelled, no_show
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    lead = relationship("Lead", back_populates="meetings")


class Trial(Base):
    __tablename__ = "trials"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    program_name = Column(String(255), default="ActTrident 90-Day Free Evaluation")
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    devices_count = Column(Integer, default=5)
    status = Column(String(50), default="active")  # active, completed, converted, cancelled
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    lead = relationship("Lead", back_populates="trials")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)
    contract_start = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    managed_devices = Column(Integer, default=5)
    subscription_plan = Column(String(100), default="Enterprise")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
