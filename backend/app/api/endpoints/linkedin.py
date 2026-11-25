from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.integrations.linkedin_adapter import (
    get_linkedin_connection_status,
    LinkedInIntegrationError,
)
from app.models.user import User
from app.schemas.linkedin import (
    LinkedInDraftCreate,
    LinkedInDraftUpdate,
    LinkedInManualSendConfirmRequest,
    LinkedInMessageResponse,
    LinkedInRejectRequest,
)
from app.services.linkedin_service import (
    approve_linkedin_message,
    confirm_linkedin_manual_send,
    create_linkedin_draft,
    dispatch_approved_linkedin_message,
    list_linkedin_messages,
    reject_linkedin_message,
    update_linkedin_draft,
)

router = APIRouter()


@router.get("/status")
def linkedin_channel_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns honest LinkedIn OAuth 2.0 & Partner Messaging API status."""
    return get_linkedin_connection_status(db)


@router.get("/messages", response_model=List[LinkedInMessageResponse])
def get_linkedin_messages(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_linkedin_messages(db, status_filter=status_filter)


@router.post("/draft", response_model=LinkedInMessageResponse, status_code=status.HTTP_201_CREATED)
def draft_linkedin_message(
    draft_in: LinkedInDraftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        msg = create_linkedin_draft(db=db, draft_in=draft_in, user_id=current_user.id)
        return {
            **LinkedInMessageResponse.model_validate(msg).model_dump(),
            "company_name": msg.company.name if msg.company else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/messages/{message_id}", response_model=LinkedInMessageResponse)
def edit_linkedin_message(
    message_id: int,
    updates: LinkedInDraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates a LinkedIn draft. Editing an approved draft automatically invalidates its approval."""
    try:
        msg = update_linkedin_draft(db=db, message_id=message_id, updates=updates, user_id=current_user.id)
        return {
            **LinkedInMessageResponse.model_validate(msg).model_dump(),
            "company_name": msg.company.name if msg.company else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/approve/{message_id}", response_model=LinkedInMessageResponse)
def approve_linkedin_draft(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    try:
        msg = approve_linkedin_message(db=db, message_id=message_id, approver_user_id=current_user.id)
        return {
            **LinkedInMessageResponse.model_validate(msg).model_dump(),
            "company_name": msg.company.name if msg.company else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/reject/{message_id}", response_model=LinkedInMessageResponse)
def reject_linkedin_draft(
    message_id: int,
    req: LinkedInRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    try:
        msg = reject_linkedin_message(db=db, message_id=message_id, reviewer_user_id=current_user.id, reason=req.reason)
        return {
            **LinkedInMessageResponse.model_validate(msg).model_dump(),
            "company_name": msg.company.name if msg.company else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/dispatch/{message_id}")
def dispatch_linkedin_draft(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """
    Dispatches an approved LinkedIn message:
    - If LinkedIn Partner Messaging API is not approved, prepares compliant human-assisted handoff ('ready_for_manual_send').
    - If officially approved & OAuth connected, dispatches via authorized Partner API.
    """
    try:
        return dispatch_approved_linkedin_message(db=db, message_id=message_id, user_id=current_user.id)
    except LinkedInIntegrationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/confirm-manual-send/{message_id}", response_model=LinkedInMessageResponse)
def confirm_manual_linkedin_send(
    message_id: int,
    req: LinkedInManualSendConfirmRequest = LinkedInManualSendConfirmRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Records human confirmation that an approved LinkedIn message was manually sent inside LinkedIn."""
    try:
        msg = confirm_linkedin_manual_send(db=db, message_id=message_id, user_id=current_user.id, notes=req.notes)
        return {
            **LinkedInMessageResponse.model_validate(msg).model_dump(),
            "company_name": msg.company.name if msg.company else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
