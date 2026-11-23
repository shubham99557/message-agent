from datetime import datetime, timezone
from typing import List, Optional, Tuple, Any
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
    lead = get_lead(db, lead_id)
    followup = Followup(
        lead_id=lead_id,
        company_id=followup_in.company_id or (lead.company_id if lead else None),
        scheduled_date=followup_in.scheduled_date,
        due_date=followup_in.due_date or followup_in.scheduled_date,
        suggested_channel=followup_in.suggested_channel,
        reminder_at=followup_in.reminder_at,
        reason=followup_in.reason,
        next_action=followup_in.next_action,
        assigned_user_id=followup_in.assigned_user_id,
        notes=followup_in.notes,
        status="pending"
    )
    db.add(followup)

    # Update next followup date on lead and company
    if lead:
        lead.next_followup_date = followup_in.scheduled_date
        lead.followup_count = (lead.followup_count or 0) + 1
        if lead.company:
            lead.company.followup_status = "follow_up_due"

    db.commit()
    db.refresh(followup)
    return followup


def list_followups(
    db: Session,
    status: Optional[str] = None,
    due_only: bool = False,
    lead_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[Followup], int]:
    query = db.query(Followup)
    if lead_id:
        query = query.filter(Followup.lead_id == lead_id)
    if status:
        query = query.filter(Followup.status == status)
    if due_only:
        now = datetime.now(timezone.utc)
        query = query.filter(Followup.due_date <= now, Followup.status.in_(["pending", "not_contacted", "follow_up_due"]))
    
    total = query.count()
    items = query.order_by(Followup.scheduled_date.asc()).offset(skip).limit(limit).all()
    return items, total


def update_followup(db: Session, followup_id: int, followup_in: Any) -> Optional[Followup]:
    fu = db.query(Followup).filter(Followup.id == followup_id).first()
    if not fu:
        return None

    update_dict = followup_in.model_dump(exclude_unset=True) if hasattr(followup_in, "model_dump") else followup_in
    for field, val in update_dict.items():
        setattr(fu, field, val)

    if fu.status in ("completed", "closed", "converted") and not fu.completed_at:
        fu.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(fu)
    return fu


def delete_followup(db: Session, followup_id: int) -> bool:
    fu = db.query(Followup).filter(Followup.id == followup_id).first()
    if not fu:
        return False
    db.delete(fu)
    db.commit()
    return True


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


def execute_dpdp_erasure(db: Session, identifier: str, reason: str = "dpdp_right_to_erasure"):
    """
    Executes India DPDP Act 2023 Section 12 Right to Erasure / Right to be Forgotten:
    1. Enters identifier into SuppressionList so the individual is never re-prospected or contacted.
    2. Permanently anonymizes personal identifiers (names, emails, phones) from Company, Contact, and Lead records.
    3. Returns count of sanitized records.
    """
    clean_id = identifier.strip().lower()
    handle_opt_out(db, identifier=clean_id, channel="all", reason=reason)

    from app.models.company import Company, CompanyContact

    erased_companies = 0
    erased_contacts = 0

    comps = db.query(Company).filter(
        or_(
            Company.public_email == clean_id,
            Company.public_phone == clean_id,
            Company.public_whatsapp == clean_id
        )
    ).all()
    for comp in comps:
        comp.public_email = f"erased-{comp.id}@privacy-erased.invalid"
        comp.public_phone = None
        comp.public_whatsapp = None
        if comp.lead:
            comp.lead.pipeline_status = "do_not_contact"
            comp.lead.notes = "PII erased in compliance with DPDP Act 2023 Section 12."
        erased_companies += 1

    contacts = db.query(CompanyContact).filter(
        or_(
            CompanyContact.email == clean_id,
            CompanyContact.phone == clean_id
        )
    ).all()
    for con in contacts:
        con.first_name = "Erased"
        con.last_name = "DataSubject"
        con.email = f"erased-contact-{con.id}@privacy-erased.invalid"
        con.phone = None
        con.linkedin_url = None
        erased_contacts += 1

    db.commit()
    return {
        "status": "success",
        "identifier": clean_id,
        "erased_companies_count": erased_companies,
        "erased_contacts_count": erased_contacts,
        "message": f"Successfully executed DPDP erasure for {clean_id}."
    }
