from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.company import Company
from app.models.research import ResearchReport
from app.schemas.research import ResearchReportResponse
from app.services.research_service import generate_company_research_report
from app.services.company_service import get_company
from app.core.audit import record_audit_log

router = APIRouter()


@router.post("/company/{company_id}", response_model=ResearchReportResponse)
async def generate_research_report_endpoint(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    report = await generate_company_research_report(db, company)
    record_audit_log(
        db=db,
        action="generate_research_report",
        entity_type="research_report",
        entity_id=str(report.id),
        user_id=current_user.id,
        details={"company": company.name}
    )
    return report


@router.get("/company/{company_id}", response_model=ResearchReportResponse)
def get_research_report_endpoint(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    report = db.query(ResearchReport).filter(ResearchReport.company_id == company_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Research report not found for this company")
    return report
