from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from app.core.database import Base


class ServiceCatalogueItem(Base):
    """
    Editable, compliant ActTrident Service Catalogue.
    Defines approved capabilities, qualification signals, target profiles,
    and strictly vetted claims for AI service matching and outreach synthesis.
    """
    __tablename__ = "service_catalogue"

    id = Column(Integer, primary_key=True, index=True)
    service_code = Column(String(64), unique=True, index=True, nullable=False)
    service_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Matching rules & target profile
    target_business_types = Column(JSON, nullable=False)  # List[str] of matching industries/keywords
    common_business_problems = Column(JSON, nullable=False)  # List[str] of specific pain points solved
    required_qualification_signals = Column(JSON, nullable=False)  # Dict[str, Any] of scoring requirements
    
    # Strict Claims Boundaries
    approved_claims = Column(JSON, nullable=False)  # List[str] of legally compliant statements
    disallowed_claims = Column(JSON, nullable=False)  # List[str] of strictly prohibited exaggerations
    
    # Discovery & Outreach templates
    discovery_questions = Column(JSON, nullable=True)  # List[str] of qualification questions
    outreach_templates = Column(JSON, nullable=True)  # Dict[str, Dict[str, str]] by style (professional, concise, etc.)
    
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
