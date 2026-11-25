"""
Pydantic schemas and schema-enforcement validators for AI-generated structured data.
Guarantees deterministic structure and prevents missing-key exceptions.
"""
from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field, field_validator


class ResearchDossierOutput(BaseModel):
    summary: str = Field(..., description="Objective summary of company and operations")
    products_and_services: Optional[Union[str, List[str]]] = Field(None, description="Key commercial offerings")
    tech_stack_observations: Optional[Union[str, List[str]]] = Field(None, description="Observed tools and platforms")
    it_pain_points: Optional[Union[str, List[str]]] = Field(None, description="Potential workstation security considerations")
    relevance_score: float = Field(0.0, ge=0.0, le=100.0, description="Relevance score for ActTrident")
    confidence_rating: str = Field("low", description="high, medium, low, or unknown")
    analysis_status: str = Field("successfully_analyzed", description="successfully_analyzed, partially_analyzed, insufficient_evidence, ai_unavailable, manual_review_required")
    missing_information: List[str] = Field(default_factory=list, description="List of unverified fields")

    @field_validator("products_and_services", "tech_stack_observations", "it_pain_points", mode="after")
    @classmethod
    def normalize_list_to_string(cls, v: Any) -> Optional[str]:
        if isinstance(v, list):
            return "; ".join(str(item) for item in v if item)
        return v


class QualificationAIOutput(BaseModel):
    factor_1_tech_related: bool = False
    factor_2_at_least_5_people: bool = False
    factor_3_managed_laptops_evidence: bool = False
    factor_4_browser_workflows: bool = False
    factor_5_handles_customer_data: bool = False
    factor_6_acttrident_relevance: bool = False
    factor_7_accessible_contact: bool = False
    overall_status: str = Field("Unqualified", description="High priority, Medium priority, Needs manual verification, or Unqualified")
    score: float = Field(0.0, ge=0.0, le=100.0)
    reason: str = Field("Pending qualification analysis.")
    evidence_completeness: str = Field("pending", description="complete, partial, insufficient, or unverified")


class EmailDraftOutput(BaseModel):
    subject: str = Field(..., description="Compelling email subject line")
    body_text: str = Field(..., description="Personalized plain text email body")


class ReplyClassificationAIOutput(BaseModel):
    classification: str = Field("unknown", description="Category of response: interested, not_interested, needs_information, meeting_requested, out_of_office, unsubscribe, bounce, unknown")
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    reason: str = Field("Pending classification analysis.", description="Explanation of classification")
    suggested_response: Optional[str] = Field(None, description="Suggested reply draft")
    is_actionable: bool = Field(False, description="Whether immediate human action is required")


def parse_and_validate_schema(raw_dict: Dict[str, Any], schema_cls: type[BaseModel]) -> BaseModel:
    """Validates raw dictionary against Pydantic schema, applying safe defaults on partial matches."""
    return schema_cls.model_validate(raw_dict)
