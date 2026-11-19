from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User
from app.models.campaign import Campaign, CampaignRecipient, CAMPAIGN_STATUSES
from app.models.email import EmailDraft
from app.models.company import Company
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignResponse, CampaignRecipientResponse
from app.services.email_generator_service import generate_email_draft
from app.services.email_sender_service import send_approved_email
from app.services.orchestration_service import (
    pause_campaign,
    resume_campaign,
    stop_campaign,
    is_kill_switch_active,
    check_campaign_allows_dispatch,
    enqueue_outbox_dispatch,
)
from app.core.audit import record_audit_log

router = APIRouter()


class AddRecipientsPayload(BaseModel):
    company_ids: List[int]


class BatchDraftPayload(BaseModel):
    tone: str = "Friendly professional"
    custom_notes: Optional[str] = None


def enrich_campaign_response(db: Session, c: Campaign) -> CampaignResponse:
    recipients_count = len(c.recipients)
    drafted = db.query(EmailDraft).filter(EmailDraft.campaign_id == c.id).count()
    approved = db.query(EmailDraft).filter(
        EmailDraft.campaign_id == c.id,
        EmailDraft.approval_status == "approved"
    ).count()
    sent = db.query(EmailDraft).filter(
        EmailDraft.campaign_id == c.id,
        EmailDraft.approval_status == "sent"
    ).count()

    return CampaignResponse(
        id=c.id,
        name=c.name,
        objective=c.objective,
        target_city=c.target_city,
        target_industry=c.target_industry,
        status=c.status,
        business_type=getattr(c, "business_type", None),
        company_size=getattr(c, "company_size", None),
        min_devices=getattr(c, "min_devices", 5) or 5,
        min_score=getattr(c, "min_score", 0.0) or 0.0,
        allowed_channels=getattr(c, "allowed_channels", "email,whatsapp,linkedin") or "email,whatsapp,linkedin",
        daily_email_limit=c.daily_email_limit,
        daily_whatsapp_limit=c.daily_whatsapp_limit,
        total_email_limit=getattr(c, "total_email_limit", None),
        sending_schedule=c.sending_schedule,
        start_date=getattr(c, "start_date", None),
        end_date=getattr(c, "end_date", None),
        created_at=c.created_at,
        updated_at=c.updated_at,
        recipients_count=recipients_count,
        emails_drafted=drafted,
        emails_approved=approved,
        emails_sent=sent
    )


@router.get("", response_model=List[CampaignResponse])
def list_campaigns(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    city: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Campaign)
    if status_filter:
        query = query.filter(Campaign.status == status_filter)
    if city:
        query = query.filter(Campaign.target_city == city)
    campaigns = query.order_by(Campaign.created_at.desc()).offset(skip).limit(limit).all()
    return [enrich_campaign_response(db, c) for c in campaigns]


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    camp_in: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    camp = Campaign(
        name=camp_in.name,
        objective=camp_in.objective,
        target_city=camp_in.target_city,
        target_industry=camp_in.target_industry,
        status=camp_in.status if camp_in.status in CAMPAIGN_STATUSES else "draft",
        business_type=camp_in.business_type,
        company_size=camp_in.company_size,
        min_devices=camp_in.min_devices if camp_in.min_devices is not None else 5,
        min_score=camp_in.min_score if camp_in.min_score is not None else 0.0,
        allowed_channels=camp_in.allowed_channels or "email,whatsapp,linkedin",
        daily_email_limit=camp_in.daily_email_limit or 50,
        daily_whatsapp_limit=camp_in.daily_whatsapp_limit or 20,
        total_email_limit=camp_in.total_email_limit,
        sending_schedule=camp_in.sending_schedule or "09:00-18:00 IST Weekdays",
        start_date=camp_in.start_date,
        end_date=camp_in.end_date,
        created_by_id=current_user.id
    )
    db.add(camp)
    db.commit()
    db.refresh(camp)

    record_audit_log(
        db=db,
        action="create_campaign",
        entity_type="campaign",
        entity_id=str(camp.id),
        user_id=current_user.id,
        details={"name": camp.name, "city": camp.target_city}
    )
    return enrich_campaign_response(db, camp)


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return enrich_campaign_response(db, camp)


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: int,
    camp_update: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Ownership check
    if current_user.role not in ["admin", "manager"]:
        if camp.created_by_id and camp.created_by_id != current_user.id:
            raise HTTPException(status_code=403, detail="Permission denied: You do not own this campaign.")

    update_data = camp_update.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(camp, field, val)
    db.commit()
    db.refresh(camp)
    return enrich_campaign_response(db, camp)


@router.post("/{campaign_id}/recipients", response_model=dict)
def add_recipients_to_campaign(
    campaign_id: int,
    payload: AddRecipientsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if current_user.role not in ["admin", "manager"] and camp.created_by_id and camp.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied: You do not own this campaign.")

    added_count = 0
    for comp_id in payload.company_ids:
        comp = db.query(Company).filter(Company.id == comp_id).first()
        if not comp:
            raise HTTPException(status_code=404, detail=f"Company {comp_id} not found.")
        if comp.is_demo or getattr(comp, "verification_status", None) == "demo_fixture":
            raise HTTPException(
                status_code=400,
                detail=f"Demo fixture company '{comp.name}' cannot be added to campaigns.",
            )
        if camp.status in ("active", "running") and camp.min_devices and camp.min_devices >= 5:
            if not comp.has_verified_5_plus_laptops or getattr(comp, "verification_status", None) != "verified":
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot add company '{comp.name}' with unverified fleet status ({getattr(comp, 'verification_status', 'pending')}) to a live campaign requiring verified devices.",
                )
        exists = db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.company_id == comp_id
        ).first()
        if not exists:
            recip = CampaignRecipient(
                campaign_id=campaign_id,
                company_id=comp_id,
                status="pending"
            )
            db.add(recip)
            added_count += 1
    db.commit()
    return {
        "status": "success",
        "added_count": added_count,
        "added_recipients": added_count,
        "campaign_id": campaign_id
    }


@router.get("/{campaign_id}/recipients", response_model=List[CampaignRecipientResponse])
def get_campaign_recipients(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    recipients = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id).all()
    results = []
    for r in recipients:
        comp = r.company
        results.append(CampaignRecipientResponse(
            id=r.id,
            campaign_id=r.campaign_id,
            company_id=r.company_id,
            company_name=comp.name if comp else None,
            company_city=comp.city if comp else None,
            status=r.status,
            scheduled_at=r.scheduled_at,
            sent_at=r.sent_at,
            created_at=r.created_at
        ))
    return results


@router.post("/{campaign_id}/batch-draft", response_model=dict)
@router.post("/{campaign_id}/generate-drafts", response_model=dict)
def batch_generate_campaign_drafts(
    campaign_id: int,
    payload: BatchDraftPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if current_user.role not in ["admin", "manager"] and camp.created_by_id and camp.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied: You do not own this campaign.")

    recipients = db.query(CampaignRecipient).filter(
        CampaignRecipient.campaign_id == campaign_id,
        CampaignRecipient.status == "pending"
    ).all()

    drafted = 0
    for r in recipients:
        if r.company:
            generate_email_draft(
                db=db,
                company=r.company,
                contact_id=r.contact_id,
                campaign_id=campaign_id,
                tone=payload.tone,
                custom_notes=payload.custom_notes
            )
            r.status = "email_drafted"
            drafted += 1
    db.commit()
    return {
        "status": "success",
        "drafted_count": drafted,
        "drafts_created": drafted,
        "campaign_id": campaign_id
    }


@router.post("/{campaign_id}/pause", response_model=dict)
def pause_campaign_endpoint(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Pauses a campaign immediately and cancels any pending queued outbox items."""
    try:
        camp, cancelled = pause_campaign(db=db, campaign_id=campaign_id, user_id=current_user.id)
        return {
            "id": camp.id,
            "status": camp.status,
            "cancelled_outbox_items": cancelled,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{campaign_id}/resume", response_model=dict)
def resume_campaign_endpoint(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Resumes a paused or draft campaign to 'active' (permanently stopped campaigns cannot be resumed)."""
    try:
        camp = resume_campaign(db=db, campaign_id=campaign_id, user_id=current_user.id)
        return {"id": camp.id, "status": camp.status}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{campaign_id}/stop", response_model=dict)
def stop_campaign_endpoint(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Permanently stops a campaign and cancels all pending outbox items."""
    try:
        camp, cancelled = stop_campaign(db=db, campaign_id=campaign_id, user_id=current_user.id)
        return {
            "id": camp.id,
            "status": camp.status,
            "cancelled_outbox_items": cancelled,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{campaign_id}/enqueue-approved", response_model=dict)
def enqueue_approved_campaign_emails(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Enqueues approved campaign drafts into the crash-safe transactional OutboundDispatchOutbox."""
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    ks_active, ks_reason = is_kill_switch_active(db)
    if ks_active:
        raise HTTPException(status_code=423, detail=f"Global Outbound Kill Switch is ACTIVE: {ks_reason}")

    camp_ok, camp_err = check_campaign_allows_dispatch(db, campaign_id)
    if not camp_ok:
        raise HTTPException(status_code=409, detail=camp_err)

    approved_drafts = db.query(EmailDraft).filter(
        EmailDraft.campaign_id == campaign_id,
        EmailDraft.approval_status == "approved"
    ).limit(camp.daily_email_limit).all()

    enqueued_ids = []
    for d in approved_drafts:
        row = enqueue_outbox_dispatch(
            db=db,
            channel="email",
            entity_id=d.id,
            user_id=current_user.id,
            campaign_id=campaign_id,
        )
        enqueued_ids.append(row.id)

    return {
        "status": "enqueued",
        "campaign_id": campaign_id,
        "enqueued_count": len(enqueued_ids),
        "outbox_ids": enqueued_ids,
    }


@router.post("/{campaign_id}/dispatch-approved", response_model=dict)
@router.post("/{campaign_id}/send-approved", response_model=dict)
def dispatch_approved_campaign_emails(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    ks_active, ks_reason = is_kill_switch_active(db)
    if ks_active:
        raise HTTPException(status_code=423, detail=f"Global Outbound Kill Switch is ACTIVE: {ks_reason}")

    camp_ok, camp_err = check_campaign_allows_dispatch(db, campaign_id)
    if not camp_ok:
        raise HTTPException(status_code=409, detail=camp_err)

    approved_drafts = db.query(EmailDraft).filter(
        EmailDraft.campaign_id == campaign_id,
        EmailDraft.approval_status == "approved"
    ).limit(camp.daily_email_limit).all()

    sent = 0
    simulated = 0
    failed = 0
    for d in approved_drafts:
        res = send_approved_email(db, d.id, current_user.id)
        if res.status == "sent":
            sent += 1
        elif res.status == "simulated":
            simulated += 1
        else:
            failed += 1

    return {
        "status": "completed",
        "sent_count": sent,
        "simulated_count": simulated,
        "sent": sent,
        "simulated": simulated,
        "failed_count": failed
    }
