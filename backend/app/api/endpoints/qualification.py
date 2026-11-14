from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.company import Company
from app.schemas.research import QualificationResult
from app.services.qualification_service import qualify_company
from app.services.company_service import get_company
from app.core.audit import record_audit_log

router = APIRouter()


@router.post("/company/{company_id}", response_model=QualificationResult)
def run_lead_qualification(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    result = qualify_company(db, company)
    record_audit_log(
        db=db,
        action="qualify_company",
        entity_type="company",
        entity_id=str(company.id),
        user_id=current_user.id,
        details={"score": result.score, "status": result.status}
    )
    return result


@router.post("/batch", response_model=List[QualificationResult])
def run_batch_qualification(
    company_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    results = []
    for cid in company_ids:
        company = get_company(db, cid)
        if company:
            res = qualify_company(db, company)
            results.append(res)
    return results


@router.post("/reverify-stale", response_model=List[QualificationResult])
def reverify_stale_leads(
    max_age_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Scans and re-qualifies leads with qualification records older than max_age_days."""
    from app.services.qualification_service import reverify_stale_qualifications
    return reverify_stale_qualifications(db, max_age_days=max_age_days)
