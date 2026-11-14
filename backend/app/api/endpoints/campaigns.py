from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).offset(skip).limit(limit).all()
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
        status="draft",  # Default state is draft!
        daily_email_limit=camp_in.daily_email_limit,
        daily_whatsapp_limit=camp_in.daily_whatsapp_limit,
        sending_schedule=camp_in.sending_schedule
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

    added = 0
    for cid in payload.company_ids:
        exists = db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.company_id == cid
        ).first()
        if not exists:
            rec = CampaignRecipient(campaign_id=campaign_id, company_id=cid, status="pending")
            db.add(rec)
            added += 1

    db.commit()
    return {"status": "success", "added_recipients": added}


@router.post("/{campaign_id}/generate-drafts", response_model=dict)
def generate_drafts_for_campaign(
    campaign_id: int,
    payload: BatchDraftPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    drafted = 0
    for rec in camp.recipients:
        # Check if draft already exists
        existing = db.query(EmailDraft).filter(
            EmailDraft.campaign_id == campaign_id,
            EmailDraft.company_id == rec.company_id
        ).first()
        if not existing and rec.company:
            generate_email_draft(
                db=db,
                company=rec.company,
                contact_id=rec.contact_id,
                campaign_id=campaign_id,
                tone=payload.tone,
                custom_notes=payload.custom_notes
            )
            rec.status = "email_drafted"
            drafted += 1

    db.commit()
    return {"status": "success", "drafts_created": drafted}


@router.post("/{campaign_id}/send-approved", response_model=dict)
def send_approved_campaign_emails(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    approved_drafts = db.query(EmailDraft).filter(
        EmailDraft.campaign_id == campaign_id,
        EmailDraft.approval_status == "approved"
    ).all()

    sent_count = 0
    errors = []

    for draft in approved_drafts:
        result = send_approved_email(db, draft.id, current_user.id)
        if result.status == "sent":
            sent_count += 1
        elif result.status != "sent":
            errors.append(f"Draft {draft.id}: {result.message}")

    return {
        "status": "completed",
        "attempted": len(approved_drafts),
        "sent": sent_count,
        "errors": errors
    }
