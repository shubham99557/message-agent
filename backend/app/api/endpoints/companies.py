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
