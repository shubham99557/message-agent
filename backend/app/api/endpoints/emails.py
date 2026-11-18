from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User
from app.models.email import EmailDraft
from app.schemas.email import (
    EmailGenerateRequest,
    EmailDraftResponse,
    EmailDraftUpdate,
    EmailSendResult
)
from app.services.email_generator_service import generate_email_draft
from app.services.approval_service import enrich_draft_response, edit_email_draft
from app.services.email_sender_service import send_approved_email
from app.services.company_service import get_company
from app.core.audit import record_audit_log

router = APIRouter()


@router.post("/generate", response_model=EmailDraftResponse, status_code=status.HTTP_201_CREATED)
def generate_email_endpoint(
    req: EmailGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company = get_company(db, req.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    draft = generate_email_draft(
        db=db,
        company=company,
        contact_id=req.contact_id,
        campaign_id=req.campaign_id,
        tone=req.tone,
        custom_notes=req.custom_notes
    )
    
    record_audit_log(
        db=db,
        action="generate_email_draft",
        entity_type="email_draft",
        entity_id=str(draft.id),
        user_id=current_user.id,
        details={"company": company.name, "tone": req.tone}
    )
    return enrich_draft_response(db, draft)


@router.get("/drafts/{draft_id}", response_model=EmailDraftResponse)
def get_email_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return enrich_draft_response(db, draft)


@router.put("/drafts/{draft_id}", response_model=EmailDraftResponse)
def update_email_draft_endpoint(
    draft_id: int,
    update_in: EmailDraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    draft = edit_email_draft(
        db=db,
        draft_id=draft_id,
        update_in=update_in,
        user_id=current_user.id,
        user_role=current_user.role
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    record_audit_log(
        db=db,
        action="update_email_draft",
        entity_type="email_draft",
        entity_id=str(draft.id),
        user_id=current_user.id,
        details={"new_version": draft.version, "approval_status": draft.approval_status}
    )
    return enrich_draft_response(db, draft)


@router.post("/send/{draft_id}", response_model=EmailSendResult)
def send_email_endpoint(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    result = send_approved_email(db, draft_id, current_user.id)
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.message)
    return result
