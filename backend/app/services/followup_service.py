import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.lead import Lead, Followup
from app.models.company import Company
from app.models.activity import SuppressionList
from app.models.consent import ContactConsent
from app.models.email import EmailDraft
from app.models.whatsapp import WhatsAppMessage
from app.services.email_generator_service import generate_email_draft
from app.services.whatsapp_service import generate_whatsapp_draft, check_contact_consent

logger = logging.getLogger(__name__)

# Cadence intervals in days
CADENCE_DAYS = {
    1: 3,  # Touch 2 is 3 days after Touch 1 (Day 4)
    2: 5,  # Touch 3 is 5 days after Touch 2 (Day 9)
}

CADENCE_TONES = {
    1: "friendly_professional",
    2: "technical",
    3: "formal"
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
        suppressed = db.query(SuppressionList).filter(
            (SuppressionList.company_id == company.id) |
            (SuppressionList.identifier == (company.public_email or "").strip().lower())
        ).first()
        if suppressed:
            lead.pipeline_status = "do_not_contact"
            lead.notes = f"{(lead.notes or '')}\nStopped follow-ups: on suppression list ({suppressed.reason})".strip()
            db.commit()
            continue

        # 2. Check timing against cadence
        last_contact = lead.last_contact_date or lead.updated_at
        touch_num = (lead.followup_count or 0) + 1
        wait_days = CADENCE_DAYS.get(touch_num, 3)

        if (now - last_contact) < timedelta(days=wait_days):
            continue  # Not yet due for next touch

        # 3. Determine Channel (Channel Switching)
        # Touch 2: If WhatsApp consent verified, try WhatsApp; otherwise Email
        has_wa_consent = False
        target_phone = company.public_whatsapp or company.public_phone
        if target_phone:
            has_wa_consent = check_contact_consent(db, target_phone, channel="whatsapp")

        channel = "whatsapp" if (touch_num == 2 and has_wa_consent) else "email"
        tone = CADENCE_TONES.get(touch_num, "friendly_professional")

        # 4. Generate Draft
        if channel == "whatsapp" and target_phone:
            wa_draft = generate_whatsapp_draft(
                db=db,
                company=company,
                recipient_phone=target_phone,
                template_name="acttrident_followup_formal"
            )
            created_draft_id = f"wa-{wa_draft.id}"
        else:
            channel = "email"
            email_draft = generate_email_draft(
                db=db,
                company=company,
                campaign=None,
                style=tone
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
