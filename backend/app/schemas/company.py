from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, HttpUrl, ConfigDict


class ContactSourceBase(BaseModel):
    field_name: str
    source_url: str
    source_type: str = "official_website"
    notes: Optional[str] = None


class ContactSourceCreate(ContactSourceBase):
    company_id: int
    contact_id: Optional[int] = None


class ContactSourceResponse(ContactSourceBase):
    id: int
    company_id: int
    contact_id: Optional[int] = None
    retrieved_at: Optional[datetime] = None
    confidence: Optional[float] = 1.0
    model_config = ConfigDict(from_attributes=True)


class CompanyContactBase(BaseModel):
    name: str
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_primary: bool = False


class CompanyContactCreate(CompanyContactBase):
    company_id: int


class CompanyContactResponse(CompanyContactBase):
    id: int
    company_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CompanyBase(BaseModel):
    name: str
    website: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    city: str
    state: Optional[str] = None
    country: str = "India"
    
    employee_count_min: Optional[int] = None
    employee_count_max: Optional[int] = None
    employee_size_evidence: Optional[str] = None
    
    laptop_count_verified: Optional[int] = None
    laptop_count_evidence: Optional[str] = None
    has_verified_5_plus_laptops: bool = False
    
    public_email: Optional[str] = None
    public_phone: Optional[str] = None
    public_whatsapp: Optional[str] = None
    linkedin_url: Optional[str] = None
    
    decision_maker_name: Optional[str] = None
    decision_maker_role: Optional[str] = None
    decision_maker_email: Optional[str] = None
    decision_maker_linkedin: Optional[str] = None
    is_demo: bool = False


class CompanyCreate(CompanyBase):
    source_url: Optional[str] = None
    source_notes: Optional[str] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    employee_count_min: Optional[int] = None
    employee_count_max: Optional[int] = None
    employee_size_evidence: Optional[str] = None
    laptop_count_verified: Optional[int] = None
    laptop_count_evidence: Optional[str] = None
    has_verified_5_plus_laptops: Optional[bool] = None
    public_email: Optional[str] = None
    public_phone: Optional[str] = None
    public_whatsapp: Optional[str] = None
    linkedin_url: Optional[str] = None
    decision_maker_name: Optional[str] = None
    decision_maker_role: Optional[str] = None
    decision_maker_email: Optional[str] = None
    decision_maker_linkedin: Optional[str] = None
    qualification_status: Optional[str] = None
    qualification_score: Optional[float] = None
    qualification_reason: Optional[str] = None
    is_demo: Optional[bool] = None


class CompanyResponse(CompanyBase):
    id: int
    qualification_score: float
    qualification_status: str
    qualification_reason: Optional[str] = None
    qualification_factors: Optional[str] = None
    date_last_verified: datetime
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None
    contacts: List[CompanyContactResponse] = []
    sources: List[ContactSourceResponse] = []
    model_config = ConfigDict(from_attributes=True)


class CSVImportSummary(BaseModel):
    total_processed: int
    created_count: int
    updated_count: int
    duplicate_skipped_count: int
    errors: List[str] = []
