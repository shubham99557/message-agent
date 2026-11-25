from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.core.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    website = Column(String(512), nullable=True)
    industry = Column(String(255), nullable=True, index=True)
    description = Column(Text, nullable=True)
    city = Column(String(100), nullable=False, index=True)  # Siliguri, Gangtok, Patna, Bhagalpur, etc.
    state = Column(String(100), nullable=True)
    country = Column(String(100), default="India")
    
    # Employee size & Evidence
    employee_count_min = Column(Integer, nullable=True)
    employee_count_max = Column(Integer, nullable=True)
    employee_size_evidence = Column(Text, nullable=True)
    
    # Managed Laptops / Devices (Strictly separated from employee count!)
    laptop_count_verified = Column(Integer, nullable=True)
    laptop_count_evidence = Column(Text, nullable=True)
    laptop_fleet_status = Column(String(50), default="UNKNOWN", nullable=False)  # VERIFIED, CLAIMED, UNKNOWN
    has_verified_5_plus_laptops = Column(Boolean, default=False)
    
    # Primary public business channels
    public_email = Column(String(255), nullable=True)
    public_phone = Column(String(100), nullable=True)
    public_whatsapp = Column(String(100), nullable=True)
    linkedin_url = Column(String(512), nullable=True)
    
    # Decision Maker Details
    decision_maker_name = Column(String(255), nullable=True)
    decision_maker_role = Column(String(255), nullable=True)
    decision_maker_email = Column(String(255), nullable=True)
    decision_maker_linkedin = Column(String(512), nullable=True)
    
    # AI Qualification & Service Matching
    qualification_score = Column(Float, default=0.0)
    qualification_status = Column(String(50), default="Needs manual verification")  # High priority, Medium priority, Low priority, Not suitable, Needs manual verification
    qualification_reason = Column(Text, nullable=True)
    qualification_factors = Column(Text, nullable=True)  # JSON formatted factors
    matched_service_id = Column(Integer, ForeignKey("service_catalogue.id", ondelete="SET NULL"), nullable=True)
    matched_service_name = Column(String(255), nullable=True)
    matched_service_rationale = Column(Text, nullable=True)
    
    # Granular Verification & Authenticity Classifications
    website_classification = Column(String(50), default="unverified", nullable=True)  # authentic, likely_authentic, suspicious, parked, unrelated, unavailable, unverified
    email_verification_status = Column(String(50), default="unknown", nullable=True)  # discovered, syntax_valid, domain_checked, source_confirmed, independently_verified, invalid, unknown
    phone_verification_status = Column(String(50), default="unknown", nullable=True)  # discovered, format_valid, source_confirmed, independently_verified, invalid, unknown
    
    # Follow-Up & Operations Tracking
    followup_status = Column(String(50), default="not_contacted", nullable=True)  # not_contacted, draft_ready, awaiting_approval, approved, sent, replied, interested, not_interested, follow_up_due, converted, closed
    internal_notes = Column(Text, nullable=True)
    
    # Demo vs Real Prospect Records Separation & Provenance
    is_demo = Column(Boolean, default=False, nullable=False, index=True)
    verification_status = Column(String(50), default="unverified", nullable=False, index=True)  # verified, unverified, inferred, unknown, demo_fixture
    verification_method = Column(String(100), nullable=True)  # manual_review, official_website_crawl, csv_import, demo_fixture
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Metadata
    date_last_verified = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    created_by = relationship("User")
    contacts = relationship("CompanyContact", back_populates="company", cascade="all, delete-orphan")
    sources = relationship("ContactSource", back_populates="company", cascade="all, delete-orphan")
    consents = relationship("ContactConsent", back_populates="company", cascade="all, delete-orphan")
    research_reports = relationship("ResearchReport", back_populates="company", cascade="all, delete-orphan")
    lead = relationship("Lead", back_populates="company", uselist=False, cascade="all, delete-orphan")
    campaign_recipients = relationship("CampaignRecipient", back_populates="company")
    email_drafts = relationship("EmailDraft", back_populates="company")
    whatsapp_messages = relationship("WhatsAppMessage", back_populates="company")


class CompanyContact(Base):
    __tablename__ = "company_contacts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(100), nullable=True)
    linkedin_url = Column(String(512), nullable=True)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="contacts")
    consents = relationship("ContactConsent", back_populates="contact", cascade="all, delete-orphan")


class ContactSource(Base):
    __tablename__ = "contact_sources"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    field_name = Column(String(100), nullable=False)  # public_email, public_phone, public_whatsapp, laptop_count, etc.
    source_url = Column(String(1024), nullable=False)
    source_type = Column(String(100), nullable=False)  # official_website, mca_registry, linkedin_public, directory
    extracted_text = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    verification_status = Column(String(50), default="unverified", nullable=False)  # verified, unverified, inferred, unknown, demo_fixture
    verification_method = Column(String(100), nullable=True)
    confidence = Column(Float, default=1.0)
    retrieved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="sources")
