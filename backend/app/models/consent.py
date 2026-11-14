from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class ContactConsent(Base):
    __tablename__ = "contact_consent"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(Integer, ForeignKey("company_contacts.id", ondelete="CASCADE"), nullable=True)
    channel = Column(String(50), nullable=False)  # "whatsapp", "email"
    consent_status = Column(String(50), default="unconsented")  # "opted_in", "unconsented", "opted_out"
    consent_source = Column(String(255), nullable=True)  # e.g., "Web Form", "Inbound WhatsApp Inquiry", "Explicit Business Request", "Public Listing (Unconsented)"
    consent_date = Column(DateTime, nullable=True)
    consent_purpose = Column(String(255), nullable=True)  # "ActTrident 90-day evaluation product inquiry"
    proof_reference = Column(String(512), nullable=True)  # URL or ID of form submission / inquiry
    opt_out_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="consents")
    contact = relationship("CompanyContact", back_populates="consents")
