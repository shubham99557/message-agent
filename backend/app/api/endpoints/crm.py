import csv
import io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User
from app.models.lead import PIPELINE_STATUSES
from app.models.company import Company
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


@router.get("/export/csv")
def export_leads_csv(
    pipeline_status: Optional[str] = None,
    city: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Exports CRM pipeline leads with complete contact details, device evidence, and evaluation status."""
    leads, _ = list_leads(db, status=pipeline_status, city=city, skip=0, limit=2000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Lead ID", "Company Name", "City", "Industry", "Website",
        "Public Email", "Public Phone", "Decision Maker", "Decision Maker Role",
        "Pipeline Status", "Verified Laptops", "Device Evidence", "Qualification Score",
        "Evaluation Status", "Evaluation Devices", "Next Followup Date", "Updated At"
    ])
    for l in leads:
        comp = l.company
        writer.writerow([
            l.id,
            comp.name if comp else "",
            comp.city if comp else "",
            comp.industry or "" if comp else "",
            comp.website or "" if comp else "",
            comp.public_email or "" if comp else "",
            comp.public_phone or "" if comp else "",
            comp.decision_maker_name or "" if comp else "",
            comp.decision_maker_role or "" if comp else "",
            l.pipeline_status,
            comp.laptop_count_verified or "" if comp else "",
            comp.laptop_count_evidence or "" if comp else "",
            comp.qualification_score if comp else 0.0,
            l.trial_status or "none",
            l.trial_device_count or "",
            l.next_followup_date.strftime("%Y-%m-%d %H:%M") if l.next_followup_date else "",
            l.updated_at.strftime("%Y-%m-%d %H:%M") if l.updated_at else ""
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=acttrident_crm_leads.csv"}
    )


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
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
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
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
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
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
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
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
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
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
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
