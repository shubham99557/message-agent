import io
import csv
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User
from app.schemas.company import (
    CompanyCreate,
    CompanyUpdate,
    CompanyVerifyRequest,
    CompanyResponse,
    ContactSourceCreate,
    ContactSourceResponse,
    CSVImportSummary
)
from app.services.company_service import (
    create_company,
    get_company,
    list_companies,
    update_company,
    verify_company_record,
    add_contact_source,
    import_companies_from_csv
)
from app.core.audit import record_audit_log

router = APIRouter()


@router.get("", response_model=dict)
def get_all_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    city: Optional[str] = None,
    state: Optional[str] = None,
    industry: Optional[str] = None,
    qualification_status: Optional[str] = None,
    has_laptops: Optional[bool] = None,
    search: Optional[str] = None,
    is_demo: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    companies, total = list_companies(
        db, skip=skip, limit=limit, city=city, state=state,
        industry=industry, qualification_status=qualification_status,
        has_laptops=has_laptops, search=search, is_demo=is_demo
    )
    return {
        "items": [CompanyResponse.model_validate(c) for c in companies],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_new_company(
    comp_in: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    company = create_company(db, comp_in, user_id=current_user.id)
    record_audit_log(
        db=db,
        action="create_company",
        entity_type="company",
        entity_id=str(company.id),
        user_id=current_user.id,
        details={"name": company.name, "city": company.city, "is_demo": company.is_demo}
    )
    return company


@router.get("/contact-quality-summary")
def get_contact_quality_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read-only CRM contact quality summary over genuine prospects (preserves all verification statuses)."""
    from app.models.company import Company, ContactSource

    genuine = (
        db.query(Company)
        .filter(
            Company.is_demo == False,
            ~Company.verification_status.in_(["synthetic_fixture", "demo_fixture", "historical_test"]),
        )
        .all()
    )
    genuine_ids = [c.id for c in genuine]
    sources = (
        db.query(ContactSource)
        .filter(ContactSource.company_id.in_(genuine_ids), ContactSource.field_name == "public_email")
        .all()
        if genuine_ids
        else []
    )
    sources_by_company = {}
    for s in sources:
        sources_by_company.setdefault(s.company_id, []).append(s)

    without_public_email = sum(1 for c in genuine if not (c.public_email or "").strip())
    publicly_discovered = sum(1 for c in genuine if (c.public_email or "").strip())
    syntax_valid = sum(
        1 for c in genuine
        if (c.public_email or "").strip() and c.email_verification_status in ("syntax_valid", "domain_checked", "independently_verified")
    )
    mx_checked = sum(
        1 for c in genuine
        if (c.public_email or "").strip() and c.email_verification_status in ("domain_checked", "independently_verified")
    )
    independently_verified = sum(
        1 for c in genuine
        if (c.public_email or "").strip() and c.email_verification_status == "independently_verified"
    )
    invalid = sum(1 for c in genuine if c.email_verification_status == "invalid")

    review_items = []
    for c in genuine:
        comp_srcs = sources_by_company.get(c.id, [])
        src_statuses = {(s.verification_status or "").upper() for s in comp_srcs}
        is_free_provider = any(
            (c.public_email or "").lower().endswith(dom)
            for dom in ("@gmail.com", "@yahoo.com", "@outlook.com", "@hotmail.com")
        )
        needs_rev = (
            c.email_verification_status in ("needs_review", "syntax_valid")
            or "NEEDS_REVIEW" in src_statuses
            or is_free_provider
        )
        if needs_rev and (c.public_email or "").strip():
            latest_src = comp_srcs[-1] if comp_srcs else None
            review_items.append({
                "company_id": c.id,
                "company_name": c.name,
                "email": c.public_email,
                "email_verification_status": c.email_verification_status,
                "source_url": latest_src.source_url if latest_src else c.website,
                "source_status": latest_src.verification_status if latest_src else None,
                "retrieved_at": latest_src.retrieved_at.isoformat() if latest_src and latest_src.retrieved_at else None,
            })

    return {
        "total_genuine_prospects": len(genuine),
        "without_public_email": without_public_email,
        "publicly_discovered": publicly_discovered,
        "syntax_valid": syntax_valid,
        "mx_checked": mx_checked,
        "independently_verified": independently_verified,
        "invalid": invalid,
        "needs_review": len(review_items),
        "review_items": review_items,
    }


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company_by_id(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/{company_id}", response_model=CompanyResponse)
def update_existing_company(
    company_id: int,
    comp_in: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Strict Ownership / Privilege check
    if current_user.role not in ["admin", "manager"]:
        if company.created_by_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied: You can only edit companies you created or require manager privileges."
            )

    updated = update_company(db, company_id, comp_in)
    record_audit_log(
        db=db,
        action="update_company",
        entity_type="company",
        entity_id=str(company.id),
        user_id=current_user.id
    )
    return updated


@router.post("/{company_id}/verify", response_model=CompanyResponse)
def verify_company_endpoint(
    company_id: int,
    verify_in: CompanyVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    """Records user verification and evidence corrections with strict ownership/role guard and audit trail."""
    existing = get_company(db, company_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Company not found")
    if current_user.role not in ["admin", "manager"] and existing.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Only managers/admins or the owning analyst can verify this company record.",
        )

    try:
        company = verify_company_record(db, company_id, verify_in)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    record_audit_log(
        db=db,
        action="verify_company_record",
        entity_type="company",
        entity_id=str(company.id),
        user_id=current_user.id,
        details={
            "verification_status": company.verification_status,
            "verification_method": company.verification_method,
            "notes": verify_in.notes,
        }
    )
    return company


@router.post("/{company_id}/sources", response_model=ContactSourceResponse, status_code=status.HTTP_201_CREATED)
def add_source_to_company(
    company_id: int,
    source_in: ContactSourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if current_user.role not in ["admin", "manager"] and company.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: You can only attach sources to companies you created or require manager privileges.",
        )
    source_in.company_id = company_id
    source = add_contact_source(db, source_in)
    return source


@router.post("/import-csv", response_model=CSVImportSummary)
async def upload_csv_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")
    content = await file.read()
    csv_text = content.decode("utf-8", errors="replace")
    summary = import_companies_from_csv(db, csv_text, user_id=current_user.id)
    record_audit_log(
        db=db,
        action="import_csv",
        entity_type="company",
        user_id=current_user.id,
        details=summary.model_dump()
    )
    return summary


@router.get("/export/csv")
def export_companies_csv(
    city: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    companies, _ = list_companies(db, skip=0, limit=1000, city=city)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Name", "Website", "Industry", "City", "State",
        "Public Email", "Public Phone", "WhatsApp", "Verified Laptops",
        "Laptop Evidence", "Decision Maker", "Title", "Qualification", "Date Verified"
    ])
    for c in companies:
        writer.writerow([
            c.id, c.name, c.website or "", c.industry or "", c.city, c.state or "",
            c.public_email or "", c.public_phone or "", c.public_whatsapp or "",
            c.laptop_count_verified or "", c.laptop_count_evidence or "",
            c.decision_maker_name or "", c.decision_maker_role or "",
            c.qualification_status, c.date_last_verified.strftime("%Y-%m-%d %H:%M")
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=acttrident_companies.csv"}
    )


@router.post("/{company_id}/browser-enrich")
async def browser_enrich_company_endpoint(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """
    Phase 4D Optional Operator-Triggered Browser-Assisted Public Contact Discovery.
    Never runs automatically, never scrapes LinkedIn, never bypasses CAPTCHAs/auth,
    never invents emails, and preserves existing verification statuses.
    """
    from datetime import datetime, timezone
    from app.models.company import Company, ContactSource
    from app.services.verification_service import browser_extract_company_contact

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.is_demo or company.verification_status in ("synthetic_fixture", "demo_fixture", "historical_test"):
        raise HTTPException(status_code=400, detail="Browser enrichment is prohibited for synthetic/demo records.")
    if not company.website:
        raise HTTPException(status_code=400, detail="Company has no official website URL.")

    res = await browser_extract_company_contact(company.website)
    now = datetime.now(timezone.utc)

    # Record provenance if an email was discovered and company has none yet
    if res.get("email") and not (company.public_email or "").strip():
        company.public_email = res["email"]
        status_map = {
            "DOMAIN_MX_CHECKED": "domain_checked",
            "SYNTAX_VALID": "syntax_valid",
            "NEEDS_REVIEW": "needs_review",
        }
        company.email_verification_status = status_map.get(res.get("status"), "syntax_valid")
        company.date_last_verified = now
        db.add(ContactSource(
            company_id=company.id,
            field_name="public_email",
            source_url=res.get("source_url") or company.website,
            source_type="official_website",
            extracted_text=res["email"],
            notes=f"Phase 4D browser-assisted discovery: {res.get('status')}",
            verification_status=res.get("status") or "FOUND_PUBLICLY",
            verification_method="browser_assisted_crawl",
            confidence=0.85 if res.get("status") == "DOMAIN_MX_CHECKED" else 0.65,
            retrieved_at=now,
        ))
        db.commit()

    record_audit_log(
        db=db,
        action="browser_enrich_company",
        entity_type="company",
        entity_id=str(company.id),
        user_id=current_user.id,
        details={"status": res.get("status"), "email_found": bool(res.get("email"))},
    )
    return {"company_id": company.id, "company_name": company.name, **res}
