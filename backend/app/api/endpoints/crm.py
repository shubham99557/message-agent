from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.lead import PIPELINE_STATUSES
from app.schemas.lead import (
    LeadResponse,
    LeadUpdate,
    FollowupCreate,
    FollowupResponse,
    MeetingCreate,
    MeetingResponse,
    TrialCreate,
    TrialResponse
)
from app.services.crm_service import (
    get_lead,
    list_leads,
    update_lead,
    change_lead_status,
    add_followup,
    add_meeting,
    create_trial,
    handle_opt_out
)
from app.core.audit import record_audit_log

router = APIRouter()


class StatusUpdatePayload(BaseModel):
    status: str
    notes: Optional[str] = None


class OptOutPayload(BaseModel):
    identifier: str
    channel: str = "all"
    reason: str = "user_opt_out"


@router.get("/leads", response_model=dict)
def get_leads_pipeline(
    pipeline_status: Optional[str] = None,
    city: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    leads, total = list_leads(db, status=pipeline_status, city=city, skip=skip, limit=limit)
    return {
        "items": [LeadResponse.model_validate(l) for l in leads],
        "total": total,
        "valid_statuses": PIPELINE_STATUSES
    }


@router.get("/leads/{lead_id}", response_model=LeadResponse)
def get_single_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch("/leads/{lead_id}/status", response_model=LeadResponse)
def update_pipeline_status(
    lead_id: int,
    payload: StatusUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if payload.status not in PIPELINE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid pipeline status. Must be one of: {PIPELINE_STATUSES}")
    
    lead = change_lead_status(db, lead_id, payload.status, payload.notes)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    record_audit_log(
        db=db,
        action="update_pipeline_status",
        entity_type="lead",
        entity_id=str(lead.id),
        user_id=current_user.id,
        details={"new_status": payload.status, "notes": payload.notes}
    )
    return lead


@router.post("/leads/{lead_id}/followups", response_model=FollowupResponse, status_code=status.HTTP_201_CREATED)
def schedule_lead_followup(
    lead_id: int,
    followup_in: FollowupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return add_followup(db, lead_id, followup_in)


@router.post("/leads/{lead_id}/meetings", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def schedule_lead_meeting(
    lead_id: int,
    meeting_in: MeetingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return add_meeting(db, lead_id, meeting_in)


@router.post("/leads/{lead_id}/trials", response_model=TrialResponse, status_code=status.HTTP_201_CREATED)
def activate_lead_trial(
    lead_id: int,
    trial_in: TrialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    trial = create_trial(db, lead_id, trial_in)
    record_audit_log(
        db=db,
        action="activate_90_day_evaluation",
        entity_type="trial",
        entity_id=str(trial.id),
        user_id=current_user.id,
        details={"devices": trial_in.devices_count}
    )
    return trial


@router.post("/opt-out")
def record_prospect_opt_out(
    payload: OptOutPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    handle_opt_out(db, identifier=payload.identifier, channel=payload.channel, reason=payload.reason)
    record_audit_log(
        db=db,
        action="opt_out_prospect",
        entity_type="suppression",
        entity_id=payload.identifier,
        user_id=current_user.id,
        details={"channel": payload.channel, "reason": payload.reason}
    )
    return {"status": "success", "message": f"{payload.identifier} added to global suppression list"}
