import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.lead import Lead, Followup
from app.models.activity import SuppressionList
from app.schemas.whatsapp import WhatsAppDraftRequest
from app.services.email_generator_service import generate_email_draft
from app.services.whatsapp_service import (
    create_whatsapp_message,
    verify_active_whatsapp_consent,
    seed_default_meta_templates
)

logger = logging.getLogger(__name__)

# Cadence intervals in days
CADENCE_DAYS = {
    1: 3,  # Touch 2 is 3 days after Touch 1 (Day 4)
    2: 5,  # Touch 3 is 5 days after Touch 2 (Day 9)
}

CADENCE_TONES = {
    1: "Friendly professional",
    2: "Technical",
    3: "Follow-up"
}


def process_autonomous_followups(db: Session) -> Dict[str, Any]:
    """
    Evaluates all contacted leads and schedules/generates appropriate follow-up touchpoints
    respecting multi-touch cadence, consent, suppression, and channel switching.
    """
    now = datetime.now(timezone.utc)

    # Candidate leads: currently 'contacted', followups < 3
    leads = db.query(Lead).filter(
        Lead.pipeline_status == "contacted",
        Lead.followup_count < 3
    ).all()

    processed_count = 0
    generated_drafts = []

    for lead in leads:
        company = lead.company
        if not company:
            continue

        # 1. Stop if on Suppression List
        clean_email = (company.public_email or "").strip().lower()
        suppressed = None
        if clean_email:
            suppressed = db.query(SuppressionList).filter(
                SuppressionList.identifier == clean_email
            ).first()
        if suppressed:
            lead.pipeline_status = "do_not_contact"
            lead.notes = f"{(lead.notes or '')}\nStopped follow-ups: on suppression list ({suppressed.reason})".strip()
            db.commit()
            continue

        # 2. Check timing against cadence
        last_contact = lead.last_contact_date or lead.updated_at or now
        if last_contact.tzinfo is None:
            last_contact = last_contact.replace(tzinfo=timezone.utc)
        touch_num = (lead.followup_count or 0) + 1
        wait_days = CADENCE_DAYS.get(touch_num, 3)

        if (now - last_contact) < timedelta(days=wait_days):
            continue  # Not yet due for next touch

        # 3. Determine Channel (Channel Switching)
        has_wa_consent = False
        target_phone = company.public_whatsapp or company.public_phone
        if target_phone:
            has_wa_consent, _ = verify_active_whatsapp_consent(db, company.id, target_phone)

        channel = "whatsapp" if (touch_num == 2 and has_wa_consent) else "email"
        tone = CADENCE_TONES.get(touch_num, "Follow-up")

        # 4. Generate Draft (strictly in draft status awaiting human approval)
        if channel == "whatsapp" and target_phone:
            seed_default_meta_templates(db)
            wa_req = WhatsAppDraftRequest(
                company_id=company.id,
                template_name="acttrident_followup_formal",
                recipient_phone=target_phone,
                parameters={
                    "1": company.decision_maker_name or "Team Lead",
                    "2": company.name
                }
            )
            wa_draft = create_whatsapp_message(db, company, wa_req)
            created_draft_id = f"wa-{wa_draft.id}"
        else:
            channel = "email"
            email_draft = generate_email_draft(
                db=db,
                company=company,
                campaign_id=None,
                tone=tone
            )
            email_draft.subject = f"Follow-up: ActTrident 90-Day Evaluation for {company.name}"
            db.commit()
            created_draft_id = f"email-{email_draft.id}"

        # 5. Record Followup History
        followup_rec = Followup(
            lead_id=lead.id,
            scheduled_date=now,
            status="completed",
            suggested_channel=channel,
            notes=f"Autonomous Follow-up Touch {touch_num} via {channel} ({tone} tone). Draft: {created_draft_id}"
        )
        db.add(followup_rec)

        lead.followup_count = touch_num
        lead.last_contact_date = now
        lead.next_followup_date = now + timedelta(days=CADENCE_DAYS.get(touch_num + 1, 7))
        db.commit()

        processed_count += 1
        generated_drafts.append({
            "lead_id": lead.id,
            "company": company.name,
            "touch_number": touch_num,
            "channel": channel,
            "draft_id": created_draft_id
        })

    return {
        "timestamp": now.isoformat(),
        "evaluated_leads": len(leads),
        "followups_generated": processed_count,
        "items": generated_drafts
    }
