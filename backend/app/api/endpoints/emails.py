from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User
from app.models.email import EmailDraft, EmailSendAttempt
from app.schemas.email import (
    EmailGenerateRequest,
    EmailDraftResponse,
    EmailDraftUpdate,
    EmailSendResult
)
from app.services.email_generator_service import generate_email_draft
from app.services.approval_service import enrich_draft_response, edit_email_draft
from app.services.email_sender_service import send_approved_email, record_provider_email_event
from app.services.company_service import get_company
from app.core.audit import record_audit_log

router = APIRouter()


class ProviderEmailEventPayload(BaseModel):
    provider_message_id: str
    event_type: str  # delivered, bounced, complaint, opened, clicked
    details: Optional[str] = None


@router.post("/generate", response_model=EmailDraftResponse, status_code=status.HTTP_201_CREATED)
def generate_email_endpoint(
    req: EmailGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
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
        draft_type=req.draft_type or "initial_email",
        service_id=req.service_id,
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


def _check_draft_ownership(draft: EmailDraft, current_user: User) -> None:
    """Ensures sales_rep users can only edit/inspect drafts belonging to their own companies or campaigns."""
    if current_user.role in ["admin", "manager"]:
        return
    owns_company = bool(draft.company and draft.company.created_by_id == current_user.id)
    owns_campaign = bool(draft.campaign and draft.campaign.created_by_id == current_user.id)
    if not (owns_company or owns_campaign):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: You do not own this email draft or require manager privileges.",
        )


@router.put("/drafts/{draft_id}", response_model=EmailDraftResponse)
def update_email_draft_endpoint(
    draft_id: int,
    update_in: EmailDraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    existing = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Draft not found")
    _check_draft_ownership(existing, current_user)
    if existing.approval_status in ("sending", "sent", "delivered"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit email draft in final status '{existing.approval_status}'.",
        )

    draft = edit_email_draft(
        db=db,
        draft_id=draft_id,
        update_in=update_in,
        user_id=current_user.id,
        user_role=current_user.role
    )
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
    if result.status == "rate_limited":
        raise HTTPException(status_code=429, detail=result.message)
    if result.status == "blocked_kill_switch":
        raise HTTPException(status_code=423, detail=result.message)
    if result.status == "blocked_campaign_inactive":
        raise HTTPException(status_code=409, detail=result.message)
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.message)
    return result


@router.get("/drafts/{draft_id}/attempts")
def get_draft_send_attempts(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns separate send-attempt audit records for a draft (owner or admin/manager)."""
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    _check_draft_ownership(draft, current_user)
    attempts = (
        db.query(EmailSendAttempt)
        .filter(EmailSendAttempt.draft_id == draft_id)
        .order_by(EmailSendAttempt.attempt_number.asc())
        .all()
    )
    return [
        {
            "id": a.id,
            "draft_id": a.draft_id,
            "attempt_number": a.attempt_number,
            "idempotency_key": a.idempotency_key,
            "provider": a.provider,
            "outcome": a.outcome,
            "provider_message_id": a.provider_message_id,
            "provider_thread_id": a.provider_thread_id,
            "error_code": a.error_code,
            "error_message": a.error_message,
            "created_at": a.created_at,
        }
        for a in attempts
    ]


@router.post("/events/provider")
def ingest_provider_email_event(
    payload: ProviderEmailEventPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Records a provider-confirmed delivery, bounce, or complaint event."""
    try:
        draft = record_provider_email_event(
            db=db,
            provider_message_id=payload.provider_message_id,
            event_type=payload.event_type,
            details=payload.details,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not draft:
        raise HTTPException(status_code=404, detail="No email draft matches that provider_message_id.")

    return {
        "draft_id": draft.id,
        "approval_status": draft.approval_status,
        "provider_message_id": draft.provider_message_id,
        "event_type": payload.event_type,
    }
