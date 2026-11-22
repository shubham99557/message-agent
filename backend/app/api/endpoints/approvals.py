from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.config import settings
from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User
from app.schemas.email import EmailDraftResponse, EmailDraftUpdate, BulkApprovalRequest
from app.services.approval_service import (
    list_approval_queue,
    approve_email_draft,
    reject_email_draft,
    skip_email_draft,
    edit_email_draft,
    bulk_handle_approvals,
    enrich_draft_response,
    regenerate_email_draft,
    schedule_email_draft
)
from app.core.audit import record_audit_log

router = APIRouter()


class RejectPayload(BaseModel):
    reason: Optional[str] = "Rejected during human review"


class RegeneratePayload(BaseModel):
    tone: Optional[str] = "Friendly professional"
    custom_notes: Optional[str] = None


class SchedulePayload(BaseModel):
    scheduled_at: datetime


@router.get("/queue", response_model=dict)
def get_approval_queue_endpoint(
    status: Optional[str] = "draft",
    campaign_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    items, total = list_approval_queue(
        db, status_filter=status, campaign_id=campaign_id, skip=skip, limit=limit
    )
    return {
        "items": items,
        "total": total,
        "status_filter": status
    }


@router.post("/approve/{draft_id}", response_model=EmailDraftResponse)
def approve_draft_endpoint(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Restricted to administrators and managers. Binds immutable content hash upon approval."""
    draft = approve_email_draft(db, draft_id, current_user.id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    record_audit_log(
        db=db,
        action="approve_email_draft",
        entity_type="email_draft",
        entity_id=str(draft.id),
        user_id=current_user.id,
        details={"content_hash": draft.approved_content_hash, "version": draft.version}
    )
    return enrich_draft_response(db, draft)


@router.post("/reject/{draft_id}", response_model=EmailDraftResponse)
def reject_draft_endpoint(
    draft_id: int,
    payload: RejectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    draft = reject_email_draft(db, draft_id, current_user.id, payload.reason)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    record_audit_log(
        db=db,
        action="reject_email_draft",
        entity_type="email_draft",
        entity_id=str(draft.id),
        user_id=current_user.id,
        details={"reason": payload.reason}
    )
    return enrich_draft_response(db, draft)


@router.post("/skip/{draft_id}", response_model=EmailDraftResponse)
def skip_draft_endpoint(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    draft = skip_email_draft(db, draft_id, current_user.id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return enrich_draft_response(db, draft)


@router.post("/bulk", response_model=dict)
def bulk_approve_endpoint(
    bulk_req: BulkApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Bulk approvals are strictly forbidden for outbound messages. Bulk skip/reject allowed with bounds."""
    if bulk_req.action == "approve":
        raise HTTPException(
            status_code=400,
            detail="Bulk outbound approval is strictly prohibited. Each outreach message requires individual human operator review."
        )
    if len(bulk_req.draft_ids) > 100:
        raise HTTPException(status_code=400, detail="Bulk operation limit is 100 drafts per request.")
    result = bulk_handle_approvals(db, bulk_req, current_user.id)
    record_audit_log(
        db=db,
        action=f"bulk_{bulk_req.action}_drafts",
        entity_type="email_draft",
        user_id=current_user.id,
        details={"count": len(bulk_req.draft_ids)}
    )
    return result


@router.post("/regenerate/{draft_id}", response_model=EmailDraftResponse)
def regenerate_draft_endpoint(
    draft_id: int,
    payload: RegeneratePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Regenerates AI email draft using requested tone and resets approval status to 'draft'."""
    draft = regenerate_email_draft(
        db=db,
        draft_id=draft_id,
        user_id=current_user.id,
        tone=payload.tone,
        custom_notes=payload.custom_notes
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found or cannot be regenerated in current state.")
    record_audit_log(
        db=db,
        action="regenerate_email_draft",
        entity_type="email_draft",
        entity_id=str(draft.id),
        user_id=current_user.id,
        details={"tone": payload.tone}
    )
    return enrich_draft_response(db, draft)


@router.post("/schedule/{draft_id}", response_model=EmailDraftResponse)
def schedule_draft_endpoint(
    draft_id: int,
    payload: SchedulePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Sets a scheduled delivery timestamp on an approved or reviewable draft."""
    draft = schedule_email_draft(
        db=db,
        draft_id=draft_id,
        user_id=current_user.id,
        scheduled_at=payload.scheduled_at
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    record_audit_log(
        db=db,
        action="schedule_email_draft",
        entity_type="email_draft",
        entity_id=str(draft.id),
        user_id=current_user.id,
        details={"scheduled_at": payload.scheduled_at.isoformat()}
    )
    return enrich_draft_response(db, draft)
