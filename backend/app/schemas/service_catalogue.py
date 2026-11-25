from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ServiceCatalogueBase(BaseModel):
    service_code: str = Field(..., max_length=64, description="Unique code e.g. ACT-WS-01")
    service_name: str = Field(..., max_length=255)
    description: str
    target_business_types: List[str] = Field(default_factory=list)
    common_business_problems: List[str] = Field(default_factory=list)
    required_qualification_signals: Dict[str, Any] = Field(default_factory=dict)
    approved_claims: List[str] = Field(default_factory=list)
    disallowed_claims: List[str] = Field(default_factory=list)
    discovery_questions: Optional[List[str]] = Field(default_factory=list)
    outreach_templates: Optional[Dict[str, Dict[str, str]]] = Field(default_factory=dict)
    is_active: bool = True


class ServiceCatalogueCreate(ServiceCatalogueBase):
    pass


class ServiceCatalogueUpdate(BaseModel):
    service_name: Optional[str] = None
    description: Optional[str] = None
    target_business_types: Optional[List[str]] = None
    common_business_problems: Optional[List[str]] = None
    required_qualification_signals: Optional[Dict[str, Any]] = None
    approved_claims: Optional[List[str]] = None
    disallowed_claims: Optional[List[str]] = None
    discovery_questions: Optional[List[str]] = None
    outreach_templates: Optional[Dict[str, Dict[str, str]]] = None
    is_active: Optional[bool] = None


class ServiceCatalogueResponse(ServiceCatalogueBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ServiceMatchResult(BaseModel):
    service_id: Optional[int] = None
    service_code: Optional[str] = None
    service_name: str
    match_confidence: float
    rationale: str
    recommended_outreach_angle: str
    evidence_supporting_match: Optional[str] = None
    unsupported_assumptions: List[str] = Field(default_factory=list)
