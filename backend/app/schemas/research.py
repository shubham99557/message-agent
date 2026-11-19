from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class QualificationFactorResult(BaseModel):
    factor_name: str
    passed: bool
    score_weight: float
    evidence: str
    evidence_source: Optional[str] = None
    confidence: float = 1.0
    explanation: Optional[str] = None


class QualificationResult(BaseModel):
    company_id: int
    score: float
    status: str  # High priority, Medium priority, Low priority, Not suitable, Needs manual verification
    reason: str
    factors: List[QualificationFactorResult]
    has_verified_5_plus_laptops: bool
    distinction_note: str
    recommended_next_action: str = "Proceed to outreach"
    last_verified_at: Optional[datetime] = None
    is_stale: bool = False


class ResearchReportBase(BaseModel):
    company_id: int
    summary: str
    services: Optional[str] = None
    likely_tech_requirements: Optional[str] = None
    potential_acttrident_use_cases: Optional[str] = None
    relevant_decision_maker_role: Optional[str] = None
    recommended_outreach_approach: Optional[str] = None
    sources_summary: Optional[str] = None
    missing_information: Optional[str] = None
    confidence_level: Optional[float] = 0.5


class ResearchReportResponse(ResearchReportBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DiscoveryQuery(BaseModel):
    city: str
    state: Optional[str] = None
    industry: Optional[str] = None
    query: Optional[str] = None
    min_devices: Optional[int] = 5
    include_demo: bool = True  # Explicitly separates .example.com demo fixtures from real sources


class DiscoveredCompanyItem(BaseModel):
    name: str
    website: Optional[str] = None
    city: str
    state: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    public_email: Optional[str] = None
    public_phone: Optional[str] = None
    public_whatsapp: Optional[str] = None
    linkedin_url: Optional[str] = None
    decision_maker_name: Optional[str] = None
    decision_maker_role: Optional[str] = None
    employee_count_min: Optional[int] = None
    employee_count_max: Optional[int] = None
    employee_size_evidence: Optional[str] = None
    laptop_count_verified: Optional[int] = None
    laptop_count_evidence: Optional[str] = None
    source_url: str
    source_type: str = "business_directory"
    is_demo: bool = False
    verification_status: str = "unverified"  # verified, unverified, inferred, unknown, demo_fixture
    confidence_level: float = 0.5
    retrieval_timestamp: Optional[datetime] = None


class WebsiteCrawlRequest(BaseModel):
    website_url: str
    company_name: Optional[str] = None
    city: Optional[str] = None


class BatchImportRequest(BaseModel):
    companies: List[DiscoveredCompanyItem]
