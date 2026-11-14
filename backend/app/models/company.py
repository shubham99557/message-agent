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
    
    # AI Qualification
    qualification_score = Column(Float, default=0.0)
    qualification_status = Column(String(50), default="Needs manual verification")  # High priority, Medium priority, Low priority, Not suitable, Needs manual verification
    qualification_reason = Column(Text, nullable=True)
    qualification_factors = Column(Text, nullable=True)  # JSON formatted factors
    
    # Metadata
    date_last_verified = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
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
    title = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(100), nullable=True)
    whatsapp = Column(String(100), nullable=True)
    linkedin_url = Column(String(512), nullable=True)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="contacts")
    sources = relationship("ContactSource", back_populates="contact")
    consents = relationship("ContactConsent", back_populates="contact")


class ContactSource(Base):
    __tablename__ = "contact_sources"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(Integer, ForeignKey("company_contacts.id", ondelete="SET NULL"), nullable=True)
    field_name = Column(String(100), nullable=False)  # public_email, phone, whatsapp, website, employee_size, laptop_count, etc.
    source_url = Column(String(1024), nullable=False)
    source_type = Column(String(100), default="official_website")  # official_website, public_directory, mca_portal, permitted_api
    verified_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, nullable=True)

    company = relationship("Company", back_populates="sources")
    contact = relationship("CompanyContact", back_populates="sources")
