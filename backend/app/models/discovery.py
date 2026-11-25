from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from app.core.database import Base


class DiscoveryRun(Base):
    """
    Persistent audit record of an operator or automated business discovery search.
    Records search criteria, active providers, and honest lead yield metrics.
    """
    __tablename__ = "discovery_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_uuid = Column(String(64), unique=True, index=True, nullable=False)
    query_summary = Column(String(512), nullable=False)
    city = Column(String(100), nullable=True, index=True)
    state = Column(String(100), nullable=True, index=True)
    country = Column(String(100), default="India", nullable=False)
    industry = Column(String(255), nullable=True)
    scope = Column(String(50), default="city", nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Provider transparency
    active_providers = Column(JSON, nullable=True)  # List of provider names actually queried
    failed_providers = Column(JSON, nullable=True)  # List of standby or failed providers
    
    # Honest pipeline counts
    raw_candidates_count = Column(Integer, default=0, nullable=False)
    unique_businesses_count = Column(Integer, default=0, nullable=False)
    filtered_facilities_count = Column(Integer, default=0, nullable=False)
    authentic_websites_count = Column(Integer, default=0, nullable=False)
    listed_phones_count = Column(Integer, default=0, nullable=False)
    verified_emails_count = Column(Integer, default=0, nullable=False)
    high_priority_count = Column(Integer, default=0, nullable=False)
    medium_priority_count = Column(Integer, default=0, nullable=False)
    low_priority_count = Column(Integer, default=0, nullable=False)
    
    # Execution metadata
    execution_duration_seconds = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
