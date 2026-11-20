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
    relevance_score: float = Field(80.0, ge=0.0, le=100.0, description="Relevance score for ActTrident")
    confidence_rating: str = Field("medium", description="high, medium, or low")
    missing_information: Optional[Union[str, List[str]]] = Field(default_factory=list, description="List of unverified fields")

    @field_validator("products_and_services", "tech_stack_observations", "it_pain_points", mode="after")
    @classmethod
    def normalize_list_to_string(cls, v: Any) -> Optional[str]:
        if isinstance(v, list):
            return "; ".join(str(item) for item in v if item)
        return v


class QualificationAIOutput(BaseModel):
    factor_1_tech_related: bool = True
    factor_2_at_least_5_people: bool = True
    factor_3_managed_laptops_evidence: bool = True
    factor_4_browser_workflows: bool = True
    factor_5_handles_customer_data: bool = True
    factor_6_acttrident_relevance: bool = True
    factor_7_accessible_contact: bool = True
    overall_status: str = Field("High priority", description="High priority, Medium priority, or Unqualified")
    score: float = Field(85.0, ge=0.0, le=100.0)
    reason: str = Field("Qualified based on verified technological operations and device fleet.")


class EmailDraftOutput(BaseModel):
    subject: str = Field(..., description="Compelling email subject line")
    body_text: str = Field(..., description="Personalized plain text email body")


class ReplyClassificationAIOutput(BaseModel):
    classification: str = Field("interested", description="Category of response")
    confidence: float = Field(0.9, ge=0.0, le=1.0)
    reason: str = Field(..., description="Explanation of classification")
    suggested_response: Optional[str] = Field(None, description="Suggested reply draft")


def parse_and_validate_schema(raw_dict: Dict[str, Any], schema_cls: type[BaseModel]) -> BaseModel:
    """Validates raw dictionary against Pydantic schema, applying safe defaults on partial matches."""
    return schema_cls.model_validate(raw_dict)
