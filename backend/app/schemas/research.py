from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class QualificationFactorResult(BaseModel):
    factor_name: str
    passed: bool
    score_weight: float
    evidence: str
    evidence_source: Optional[str] = None
    verification_state: str = "UNKNOWN"  # VERIFIED, CLAIMED, UNKNOWN, CONFLICTING, OUTDATED
    confidence: float = 1.0
    explanation: Optional[str] = None


class QualificationResult(BaseModel):
    company_id: int
    score: float
    status: str  # High priority, Medium priority, Low priority, Not suitable, Needs manual verification, Unqualified
    reason: str
    factors: List[QualificationFactorResult]
    has_verified_5_plus_laptops: bool
    distinction_note: str
    recommended_next_action: str = "Proceed to outreach"
    matched_service_id: Optional[int] = None
    matched_service_name: Optional[str] = None
    matched_service_rationale: Optional[str] = None
    website_classification: Optional[str] = None
    email_verification_status: Optional[str] = None
    phone_verification_status: Optional[str] = None
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
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    region: Optional[str] = None
    district: Optional[str] = None
    pincode: Optional[str] = None
    scope: Optional[str] = "city"  # "city", "state", "country", "region", "pincode"
    industry: Optional[str] = None
    query: Optional[str] = None
    min_devices: Optional[int] = None
    min_employees: Optional[int] = None
    max_employees: Optional[int] = None
    company_size: Optional[str] = None  # "all", "1-10", "11-50", "50+", "5+ employees"
    include_demo: bool = True  # Allowed in non-production; strictly blocked in production by discovery service
    page: int = 1
    page_size: int = 20
    sort_by: Optional[str] = "confidence"  # "confidence", "name", "city", "devices", "retrieval"
    sort_order: Optional[str] = "desc"


class DiscoveredCompanyItem(BaseModel):
    name: str
    website: Optional[str] = None
    city: str
    state: Optional[str] = None
    country: Optional[str] = "India"
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
    laptop_fleet_status: Optional[str] = "UNKNOWN"  # VERIFIED, CLAIMED, UNKNOWN
    source_url: str
    contact_page_url: Optional[str] = None
    business_address: Optional[str] = None
    missing_information: Optional[List[str]] = None
    source_type: str = "business_directory"
    is_demo: bool = False
    verification_status: str = "unverified"  # verified, partially_verified, unverified, inferred, unknown, demo_fixture
    email_verification_status: Optional[str] = "unverified"  # verified, publicly_listed, unverified, unavailable
    phone_verification_status: Optional[str] = "unverified"
    website_status: Optional[str] = "unverified"  # accessible, inaccessible, unverified, unavailable
    website_classification: Optional[str] = "unverified"  # authentic, likely_authentic, suspicious, parked, unrelated, unavailable, unverified
    matched_service_id: Optional[int] = None
    matched_service_name: Optional[str] = None
    matched_service_rationale: Optional[str] = None
    confidence_level: float = 0.5
    retrieval_timestamp: Optional[datetime] = None
    qualification_score: Optional[float] = None
    qualification_category: Optional[str] = None
    qualification_reason: Optional[str] = None
    qualification_factors: Optional[List[QualificationFactorResult]] = None
    crm_id: Optional[int] = None
    crm_status: Optional[str] = None
    research_summary: Optional[str] = None
    research_dossier: Optional[Dict[str, Any]] = None
    provenance_sources: Optional[List[Dict[str, Any]]] = None


class DiscoveryPipelineStep(BaseModel):
    step_number: int
    step_name: str
    status: str = "completed"  # completed, in_progress, failed, skipped
    detail: str
    timestamp: datetime


class DiscoveryPipelineRequest(BaseModel):
    industry: Optional[str] = "Software & IT Services"
    city: str = "Siliguri"
    state: Optional[str] = "West Bengal"
    country: str = "India"
    scope: Optional[str] = "city"
    query: Optional[str] = None
    target_category: Optional[str] = None
    min_devices: Optional[int] = None
    min_employees: Optional[int] = None
    company_size: Optional[str] = None
    max_leads: int = 10
    min_score: float = 40.0
    include_demo: bool = False
    auto_verify: bool = True
    auto_research: bool = True
    auto_qualify: bool = True
    auto_save_crm: bool = True
    campaign_id: Optional[int] = None  # Tag saved/matched leads as discovered for this campaign


class DiscoveryPipelineResponse(BaseModel):
    query_summary: str
    steps: List[DiscoveryPipelineStep]
    total_discovered: int
    commercial_relevant: Optional[int] = None
    websites_verified: int
    public_emails_found: int
    contacts_verified: int
    companies_researched: int
    companies_qualified: int
    high_priority_count: Optional[int] = None
    medium_priority_count: Optional[int] = None
    low_priority_count: Optional[int] = None
    saved_to_crm: int
    items: List[DiscoveredCompanyItem]
    active_providers: List[str]
    failed_providers: List[str] = []
    duration_seconds: float


class DiscoveryResponse(BaseModel):
    items: List[DiscoveredCompanyItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    scope: str
    search_strategy: str
    coverage_note: str
    active_providers: List[str]
    failed_providers: List[str] = []
    commercial_relevant: Optional[int] = None
    verified_websites: Optional[int] = None
    verified_emails: Optional[int] = None
    verified_phones: Optional[int] = None
    high_priority_count: Optional[int] = None
    medium_priority_count: Optional[int] = None
    low_priority_count: Optional[int] = None


class WebsiteCrawlRequest(BaseModel):
    website_url: str
    company_name: Optional[str] = None
    city: Optional[str] = None


class BatchImportRequest(BaseModel):
    companies: List[DiscoveredCompanyItem]
    campaign_id: Optional[int] = None


class MultiCityDiscoveryQuery(BaseModel):
    cities: List[str]
    industry: Optional[str] = None
    query: Optional[str] = None
    min_devices: Optional[int] = None
    include_demo: bool = True
    page: int = 1
    page_size: int = 20
    sort_by: Optional[str] = "confidence"
    sort_order: Optional[str] = "desc"


class DiscoverySearchHistoryItem(BaseModel):
    id: str
    query_summary: str
    city: Optional[str] = None
    state: Optional[str] = None
    scope: str
    results_count: int
    timestamp: datetime
