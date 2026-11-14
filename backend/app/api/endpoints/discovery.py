from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.research import DiscoveryQuery, DiscoveredCompanyItem
from app.schemas.company import CompanyResponse, CompanyCreate
from app.services.discovery_service import search_public_company_directory
from app.services.company_service import create_company, find_duplicate_company
from app.core.audit import record_audit_log

router = APIRouter()


@router.post("/search", response_model=List[DiscoveredCompanyItem])
def search_discovery_directory(
    query_params: DiscoveryQuery,
    current_user: User = Depends(get_current_user)
):
    results = search_public_company_directory(query_params)
    return results


@router.post("/import", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def import_discovered_lead(
    item: DiscoveredCompanyItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing = find_duplicate_company(db, name=item.name, website=item.website, email=item.public_email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Company '{item.name}' already exists in the database (ID: {existing.id})"
        )

    company_create = CompanyCreate(
        name=item.name,
        website=item.website,
        city=item.city,
        state=item.state,
        industry=item.industry,
        description=item.description,
        public_email=item.public_email,
        public_phone=item.public_phone,
        public_whatsapp=item.public_whatsapp,
        linkedin_url=item.linkedin_url,
        decision_maker_name=item.decision_maker_name,
        decision_maker_role=item.decision_maker_role,
        employee_count_min=item.employee_count_min,
        employee_count_max=item.employee_count_max,
        employee_size_evidence=item.employee_size_evidence,
        laptop_count_verified=item.laptop_count_verified,
        laptop_count_evidence=item.laptop_count_evidence,
        source_url=item.source_url,
        source_notes=f"Discovered via {item.source_type}"
    )

    company = create_company(db, company_create)
    record_audit_log(
        db=db,
        action="import_discovered_lead",
        entity_type="company",
        entity_id=str(company.id),
        user_id=current_user.id,
        details={"name": company.name, "source": item.source_url}
    )
    return company
