from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.lead import Lead, Followup, Meeting, Trial, Customer, PIPELINE_STATUSES
from app.models.activity import SuppressionList
from app.models.consent import ContactConsent
from app.schemas.lead import LeadUpdate, FollowupCreate, MeetingCreate, TrialCreate


def get_lead(db: Session, lead_id: int) -> Optional[Lead]:
    return db.query(Lead).filter(Lead.id == lead_id).first()


def get_lead_by_company(db: Session, company_id: int) -> Optional[Lead]:
    return db.query(Lead).filter(Lead.company_id == company_id).first()


def list_leads(
    db: Session,
    status: Optional[str] = None,
    city: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[Lead], int]:
    query = db.query(Lead)

    if status and status.lower() != "all":
        query = query.filter(Lead.pipeline_status == status)

    if city and city.lower() != "all":
        from app.models.company import Company
        query = query.join(Company).filter(Company.city.ilike(f"%{city}%"))

    total = query.count()
    leads = query.order_by(Lead.updated_at.desc()).offset(skip).limit(limit).all()
    return leads, total


def update_lead(db: Session, lead_id: int, lead_in: LeadUpdate) -> Optional[Lead]:
    lead = get_lead(db, lead_id)
    if not lead:
        return None

    update_data = lead_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)

    lead.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lead)
    return lead


def change_lead_status(db: Session, lead_id: int, new_status: str, notes: Optional[str] = None) -> Optional[Lead]:
    lead = get_lead(db, lead_id)
    if not lead or new_status not in PIPELINE_STATUSES:
        return None

    lead.pipeline_status = new_status
    if notes:
        lead.meeting_notes = f"{lead.meeting_notes or ''}\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {notes}".strip()
    
    lead.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lead)
    return lead


def add_followup(db: Session, lead_id: int, followup_in: FollowupCreate) -> Followup:
    followup = Followup(
        lead_id=lead_id,
        scheduled_date=followup_in.scheduled_date,
        suggested_channel=followup_in.suggested_channel,
        notes=followup_in.notes,
        status="pending"
    )
    db.add(followup)

    # Update next followup date on lead
    lead = get_lead(db, lead_id)
    if lead:
        lead.next_followup_date = followup_in.scheduled_date
        lead.followup_count = (lead.followup_count or 0) + 1

    db.commit()
    db.refresh(followup)
    return followup


def add_meeting(db: Session, lead_id: int, meeting_in: MeetingCreate) -> Meeting:
    meeting = Meeting(
        lead_id=lead_id,
        title=meeting_in.title,
        scheduled_at=meeting_in.scheduled_at,
        duration_minutes=meeting_in.duration_minutes,
        meeting_url=meeting_in.meeting_url,
        notes=meeting_in.notes,
        status="scheduled"
    )
    db.add(meeting)

    lead = get_lead(db, lead_id)
    if lead:
        lead.pipeline_status = "meeting_scheduled"

    db.commit()
    db.refresh(meeting)
    return meeting


def create_trial(db: Session, lead_id: int, trial_in: TrialCreate) -> Trial:
    trial = Trial(
        lead_id=lead_id,
        program_name=trial_in.program_name,
        start_date=trial_in.start_date,
        end_date=trial_in.end_date,
        devices_count=trial_in.devices_count,
        status="active",
        feedback=trial_in.feedback
    )
    db.add(trial)

    lead = get_lead(db, lead_id)
    if lead:
        lead.pipeline_status = "trial_activated"
        lead.trial_status = "active"
        lead.trial_start_date = trial_in.start_date
        lead.trial_end_date = trial_in.end_date
        lead.trial_device_count = trial_in.devices_count

    db.commit()
    db.refresh(trial)
    return trial


def handle_opt_out(db: Session, identifier: str, channel: str = "all", reason: str = "user_opt_out"):
    """Enforces instant suppression across CRM and contact consents upon opt-out."""
    # 1. Add to suppression list if not already present
    suppressed = db.query(SuppressionList).filter(SuppressionList.identifier == identifier.strip()).first()
    if not suppressed:
        suppressed = SuppressionList(
            identifier=identifier.strip(),
            channel=channel,
            reason=reason,
            source="opt_out_enforcement"
        )
        db.add(suppressed)

    # 2. Update company consent & pipeline status
    from app.models.company import Company
    companies = db.query(Company).filter(
        or_(
            Company.public_email == identifier.strip(),
            Company.public_phone == identifier.strip(),
            Company.public_whatsapp == identifier.strip()
        )
    ).all()

    for comp in companies:
        if comp.lead:
            comp.lead.pipeline_status = "do_not_contact"
        # Update consents
        consents = db.query(ContactConsent).filter(ContactConsent.company_id == comp.id).all()
        for c in consents:
            c.consent_status = "opted_out"
            c.opt_out_date = datetime.now(timezone.utc)

    db.commit()
