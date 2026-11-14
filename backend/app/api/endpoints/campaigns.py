from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User
from app.models.campaign import Campaign, CampaignRecipient
from app.models.email import EmailDraft
from app.models.company import Company
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignResponse, CampaignRecipientResponse
from app.services.email_generator_service import generate_email_draft
from app.services.email_sender_service import send_approved_email
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
        daily_email_limit=c.daily_email_limit,
        daily_whatsapp_limit=c.daily_whatsapp_limit,
        sending_schedule=c.sending_schedule,
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
    current_user: User = Depends(get_current_user)
):
    camp = Campaign(
        name=camp_in.name,
        objective=camp_in.objective,
        target_city=camp_in.target_city,
        target_industry=camp_in.target_industry,
        status="draft",
        daily_email_limit=camp_in.daily_email_limit or 50,
        daily_whatsapp_limit=camp_in.daily_whatsapp_limit or 20,
        sending_schedule=camp_in.sending_schedule or "09:00-18:00 IST Weekdays",
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
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
):
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    added_count = 0
    for comp_id in payload.company_ids:
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
    current_user: User = Depends(get_current_user)
):
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

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

    approved_drafts = db.query(EmailDraft).filter(
        EmailDraft.campaign_id == campaign_id,
        EmailDraft.approval_status == "approved"
    ).limit(camp.daily_email_limit).all()

    sent = 0
    failed = 0
    for d in approved_drafts:
        res = send_approved_email(db, d.id, current_user.id)
        if res.status in ["sent", "simulated"]:
            sent += 1
        else:
            failed += 1

    return {"status": "completed", "sent_count": sent, "failed_count": failed}
