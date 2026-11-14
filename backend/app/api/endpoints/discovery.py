from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.research import (
    DiscoveryQuery,
    DiscoveredCompanyItem,
    WebsiteCrawlRequest,
    BatchImportRequest
)
from app.schemas.company import CompanyResponse, CompanyCreate
from app.services.discovery_service import (
    search_public_company_directory,
    crawl_company_website_for_contacts,
    parse_csv_discovery_file
)
from app.services.company_service import create_company, find_duplicate_company
from app.core.audit import record_audit_log

router = APIRouter()


@router.post("/search", response_model=List[DiscoveredCompanyItem])
def search_discovery_directory(
    query_params: DiscoveryQuery,
    current_user: User = Depends(get_current_user)
):
    """Searches legitimate public business databases for matching target companies."""
    results = search_public_company_directory(query_params)
    return results


@router.post("/crawl-website", response_model=Dict[str, Any])
async def crawl_website(
    req: WebsiteCrawlRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Safely crawls an official company website to extract legitimate public contact details
    and workstation/team evidence snippets without SSRF vulnerability.
    """
    data = await crawl_company_website_for_contacts(req.website_url)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@router.post("/import", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def import_discovered_lead(
    item: DiscoveredCompanyItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Imports a single discovered company with full contact source attribution."""
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


@router.post("/batch-import", response_model=List[CompanyResponse])
def batch_import_discovered_leads(
    req: BatchImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Imports multiple discovered leads with deduplication and source persistence."""
    imported = []
    for item in req.companies:
        existing = find_duplicate_company(db, name=item.name, website=item.website, email=item.public_email)
        if existing:
            continue
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
        comp = create_company(db, company_create)
        imported.append(comp)

    return imported


@router.post("/upload-csv", response_model=List[DiscoveredCompanyItem])
async def upload_discovery_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Parses an uploaded CSV business list and returns structured discovered items with source attribution."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    content = await file.read()
    items = parse_csv_discovery_file(content, filename=file.filename)
    return items
