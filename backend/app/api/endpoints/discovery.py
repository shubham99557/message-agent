import io
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.services.campaign_eligibility_service import link_leads_to_campaign

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.research import (
    DiscoveryQuery,
    DiscoveredCompanyItem,
    DiscoveryResponse,
    WebsiteCrawlRequest,
    BatchImportRequest,
    MultiCityDiscoveryQuery,
    DiscoverySearchHistoryItem,
    DiscoveryPipelineRequest,
    DiscoveryPipelineResponse,
)
from app.schemas.company import CompanyResponse, CompanyCreate
from app.services.discovery_service import (
    search_public_company_directory,
    search_public_company_directory_paginated,
    search_multi_city_directory,
    get_recent_search_history,
    export_discovered_companies_csv,
    crawl_company_website_for_contacts,
    parse_csv_discovery_file,
    run_real_lead_discovery_pipeline,
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


@router.post("/pipeline", response_model=DiscoveryPipelineResponse)
async def run_lead_discovery_pipeline_endpoint(
    request_params: DiscoveryPipelineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Executes the comprehensive 10-step autonomous lead discovery, verification,
    research, qualification, and CRM ingestion workflow.
    """
    return await run_real_lead_discovery_pipeline(db, request_params)


@router.get("/history", response_model=List[DiscoverySearchHistoryItem])
def get_discovery_history(current_user: User = Depends(get_current_user)):
    """Returns recent operator discovery queries for auditability and fast re-runs."""
    return get_recent_search_history()


@router.post("/multi-city-search", response_model=DiscoveryResponse)
def search_multi_city_discovery_endpoint(
    query_params: MultiCityDiscoveryQuery,
    current_user: User = Depends(get_current_user)
):
    """Executes aggregated discovery across multiple Indian cities in a target cluster."""
    if not query_params.cities:
        raise HTTPException(status_code=400, detail="At least one target city must be specified.")
    return search_multi_city_directory(query_params)


@router.post("/export/csv")
def export_discovery_csv(
    query_params: DiscoveryQuery,
    current_user: User = Depends(get_current_user)
):
    """Exports discovered company items matching query parameters into RFC 4180 CSV format."""
    results = search_public_company_directory(query_params)
    csv_text = export_discovered_companies_csv(results)
    filename = f"discovery_export_{query_params.city or query_params.state or 'all'}_{int(len(results))}.csv"
    return StreamingResponse(
        io.StringIO(csv_text),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/coverage")
def get_geographic_coverage_metrics(current_user: User = Depends(get_current_user)):
    """Returns geographic coverage reporting across India's 6 regional zones and canonical hubs."""
    states = get_states_and_uts()
    regions = get_regions()
    return {
        "country": "India",
        "total_states_and_uts": len(states),
        "regions_covered": regions,
        "supported_strategies": ["Multi-Region Nationwide Corridors", "Targeted City Hubs", "Multi-City Clusters"],
        "status": "active"
    }


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


def _build_company_create_from_discovered(item: DiscoveredCompanyItem) -> CompanyCreate:
    return CompanyCreate(
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


def _persist_and_qualify_discovered_company(db: Session, item: DiscoveredCompanyItem, user_id: int):
    from app.models.company import ContactSource
    from app.services.qualification_service import qualify_company

    company = create_company(db, _build_company_create_from_discovered(item), user_id=user_id)
    if item.source_url and not company.sources:
        db.add(
            ContactSource(
                company_id=company.id,
                field_name="website",
                source_url=item.source_url,
                source_type=item.source_type or "public_directory",
                extracted_text=f"Discovered via {item.source_type}",
            )
        )
        db.commit()
        db.refresh(company)
    qualify_company(db, company)
    db.refresh(company)
    return company


@router.post("/import", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def import_discovered_lead(
    item: DiscoveredCompanyItem,
    campaign_id: Optional[int] = Query(None, description="Tag the lead as discovered for this campaign"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Imports a single discovered company with full contact source attribution and qualification."""
    existing = find_duplicate_company(db, name=item.name, website=item.website, email=item.public_email, source_url=item.source_url)
    if existing:
        link_leads_to_campaign(db, campaign_id, [existing.id], source="discovery_import")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Company '{item.name}' already exists in the database (ID: {existing.id})"
        )

    company = _persist_and_qualify_discovered_company(db, item, current_user.id)
    link_leads_to_campaign(db, campaign_id, [company.id], source="discovery_import")
    db.refresh(company)
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
    """Imports multiple discovered leads with deduplication, qualification, and source persistence."""
    imported = []
    linked_ids = []
    for item in req.companies:
        existing = find_duplicate_company(db, name=item.name, website=item.website, email=item.public_email, source_url=item.source_url)
        if existing:
            linked_ids.append(existing.id)
            continue
        comp = _persist_and_qualify_discovered_company(db, item, current_user.id)
        imported.append(comp)
        linked_ids.append(comp.id)

    link_leads_to_campaign(db, req.campaign_id, linked_ids, source="discovery_import")
    return imported


@router.post("/batch-import-summary")
def batch_import_discovered_leads_summary(
    req: BatchImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Imports discovered leads and returns explicit saved, duplicate-skipped, and failed counts."""
    saved_companies = []
    skipped_names = []
    failed_items = []
    linked_ids = []
    for item in req.companies:
        try:
            existing = find_duplicate_company(db, name=item.name, website=item.website, email=item.public_email, source_url=item.source_url)
            if existing:
                skipped_names.append(item.name)
                linked_ids.append(existing.id)
                continue
            comp = _persist_and_qualify_discovered_company(db, item, current_user.id)
            saved_companies.append(CompanyResponse.model_validate(comp))
            linked_ids.append(comp.id)
        except Exception as exc:
            db.rollback()
            failed_items.append({"name": item.name, "error": str(exc)})

    linked_to_campaign = link_leads_to_campaign(db, req.campaign_id, linked_ids, source="discovery_import")
    return {
        "linked_to_campaign": linked_to_campaign,
        "total_submitted": len(req.companies),
        "saved_count": len(saved_companies),
        "duplicates_skipped": len(skipped_names),
        "failed_count": len(failed_items),
        "saved_companies": saved_companies,
        "skipped_names": skipped_names,
        "failed_items": failed_items,
    }


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


@router.get("/runs", response_model=List[dict])
def get_discovery_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves persistent discovery run logs with search metrics and yield transparency."""
    from app.models.discovery import DiscoveryRun
    runs = db.query(DiscoveryRun).order_by(DiscoveryRun.created_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": r.id,
            "run_uuid": r.run_uuid,
            "query_summary": r.query_summary,
            "city": r.city,
            "state": r.state,
            "country": r.country,
            "industry": r.industry,
            "scope": r.scope,
            "campaign_id": r.campaign_id,
            "active_providers": r.active_providers,
            "raw_candidates_count": r.raw_candidates_count,
            "unique_businesses_count": r.unique_businesses_count,
            "filtered_facilities_count": r.filtered_facilities_count,
            "authentic_websites_count": r.authentic_websites_count,
            "listed_phones_count": r.listed_phones_count,
            "verified_emails_count": r.verified_emails_count,
            "high_priority_count": r.high_priority_count,
            "medium_priority_count": r.medium_priority_count,
            "low_priority_count": r.low_priority_count,
            "execution_duration_seconds": r.execution_duration_seconds,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]

