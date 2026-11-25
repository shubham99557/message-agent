from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.core.database import Base


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    summary = Column(Text, nullable=False)
    services = Column(Text, nullable=True)
    likely_tech_requirements = Column(Text, nullable=True)
    potential_acttrident_use_cases = Column(Text, nullable=True)
    relevant_decision_maker_role = Column(String(255), nullable=True)
    recommended_outreach_approach = Column(Text, nullable=True)
    sources_summary = Column(Text, nullable=True)
    missing_information = Column(Text, nullable=True)  # Explicitly enumerates unverified / unknown facts
    confidence_level = Column(Float, default=0.5, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="research_reports")
