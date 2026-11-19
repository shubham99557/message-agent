from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.research import (
    DiscoveryQuery,
    DiscoveredCompanyItem,
    DiscoveryResponse,
    WebsiteCrawlRequest,
    BatchImportRequest
)
from app.schemas.company import CompanyResponse, CompanyCreate
from app.services.discovery_service import (
    search_public_company_directory,
    search_public_company_directory_paginated,
    crawl_company_website_for_contacts,
    parse_csv_discovery_file
)
from app.core.locations import (
    get_states_and_uts,
    get_regions,
    get_presets,
    get_industries,
    search_locations,
    get_canonical_location,
)
from app.integrations.discovery_adapters import list_discovery_source_statuses
from app.services.company_service import create_company, find_duplicate_company
from app.core.audit import record_audit_log

router = APIRouter()


@router.get("/sources")
def get_discovery_sources(current_user: User = Depends(get_current_user)):
    """Returns configured status of all modular public discovery adapters."""
    return {"sources": list_discovery_source_statuses()}


@router.get("/locations/states")
def get_indian_states(current_user: User = Depends(get_current_user)):
    """Returns all 28 States and 8 Union Territories with ISO codes and regional zones."""
    return {"states": get_states_and_uts()}


@router.get("/locations/regions")
def get_indian_regions(current_user: User = Depends(get_current_user)):
    """Returns standard regional geographical groupings across India."""
    return {"regions": get_regions()}


@router.get("/locations/presets")
def get_location_presets(current_user: User = Depends(get_current_user)):
    """Returns saved location presets preserving original Siliguri/Gangtok/Patna/Bhagalpur focus."""
    return {"presets": get_presets()}


@router.get("/locations/suggest")
def suggest_locations(
    q: str = Query("", description="Debounced search query for city, state, district, or PIN prefix"),
    state: Optional[str] = Query(None, description="Filter by state name"),
    region: Optional[str] = Query(None, description="Filter by region"),
    pincode: Optional[str] = Query(None, description="Filter by PIN code prefix"),
    limit: int = Query(15, ge=1, le=50),
    current_user: User = Depends(get_current_user)
):
    """Provides debounced suggestions and autocomplete across canonical Indian cities and hubs."""
    suggestions = search_locations(query=q, state=state, region=region, pincode=pincode, limit=limit)
    return {"suggestions": suggestions}


@router.get("/industries")
def get_discovery_industry_catalog(current_user: User = Depends(get_current_user)):
    """Returns canonical business categories and keywords for targeted technology discovery."""
    return {"industries": get_industries()}


@router.post("/search", response_model=List[DiscoveredCompanyItem])
def search_discovery_directory(
    query_params: DiscoveryQuery,
    current_user: User = Depends(get_current_user)
):
    """Searches legitimate public business databases for matching target companies."""
    results = search_public_company_directory(query_params)
    return results


@router.post("/search-paginated", response_model=DiscoveryResponse)
def search_discovery_directory_paginated_endpoint(
    query_params: DiscoveryQuery,
    current_user: User = Depends(get_current_user)
):
    """
    Paginated, multi-region nationwide discovery search across canonical Indian corridors
    with provider health reporting and sorting controls.
    """
    return search_public_company_directory_paginated(query_params)


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
        source_notes=f"Discovered via {item.source_type}",
        is_demo=item.is_demo,
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
