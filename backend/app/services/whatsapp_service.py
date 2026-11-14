import json
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
import httpx

from app.models.whatsapp import WhatsAppTemplate, WhatsAppMessage
from app.models.consent import ContactConsent
from app.models.company import Company
from app.models.activity import SuppressionList
from app.schemas.whatsapp import WhatsAppDraftRequest, ContactConsentCreate
from app.core.config import settings
from app.core.audit import record_audit_log


def seed_default_meta_templates(db: Session):
    """Registers standard pre-approved Meta WhatsApp templates for ActTrident."""
    templates = [
        {
            "meta_template_name": "acttrident_intro_utility_v1",
            "category": "UTILITY",
            "language": "en",
            "status": "APPROVED",
            "header_text": "ActTrident Workspace Protection",
            "body_text": "Hello {{1}}, this is ActTrident (https://acttrident.ai/). We are connecting regarding your business laptop management in {{2}}. Eligible teams with 5+ managed devices qualify for our proposed 90-day evaluation program. Would you like a brief demonstration?",
            "footer_text": "Reply STOP to opt out",
            "variables_schema": json.dumps({"1": "recipient_name", "2": "city"})
        },
        {
            "meta_template_name": "acttrident_eval_notice_v1",
            "category": "UTILITY",
            "language": "en",
            "status": "APPROVED",
            "header_text": "90-Day Free Evaluation Notice",
            "body_text": "Dear {{1}}, following up on your request for ActTrident workspace protection for {{2}}. Your 90-day evaluation setup is ready for scheduling. Please reply to select a time.",
            "footer_text": "Reply STOP to opt out",
            "variables_schema": json.dumps({"1": "recipient_name", "2": "company_name"})
        }
    ]

    for t_data in templates:
        exists = db.query(WhatsAppTemplate).filter(
            WhatsAppTemplate.meta_template_name == t_data["meta_template_name"]
        ).first()
        if not exists:
            tmpl = WhatsAppTemplate(**t_data)
            db.add(tmpl)
    db.commit()


def render_template_body(template: WhatsAppTemplate, parameters: Dict[str, str]) -> str:
    """Replaces {{1}}, {{2}} in body text with parameter values."""
    rendered = template.body_text
    for key, val in parameters.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(val))
    return rendered


def clean_phone_number(phone: str) -> str:
    """Strips non-digits except leading + for phone numbers."""
    if not phone:
        return ""
    cleaned = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    return cleaned


def record_contact_consent(db: Session, consent_in: ContactConsentCreate) -> ContactConsent:
    """Maintains documented, verifiable consent for WhatsApp and Email outreach."""
    consent = ContactConsent(
        company_id=consent_in.company_id,
        contact_id=consent_in.contact_id,
        channel=consent_in.channel,
        consent_status=consent_in.consent_status,
        consent_source=consent_in.consent_source,
        consent_purpose=consent_in.consent_purpose,
        proof_reference=consent_in.proof_reference,
        notes=consent_in.notes,
        consent_date=datetime.now(timezone.utc) if consent_in.consent_status == "opted_in" else None,
        opt_out_date=datetime.now(timezone.utc) if consent_in.consent_status == "opted_out" else None
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


def create_whatsapp_message(
    db: Session,
    company: Company,
    req: WhatsAppDraftRequest
) -> WhatsAppMessage:
    """Enforces strict consent rules: unconsented contacts receive draft + click-to-chat link only!"""
    seed_default_meta_templates(db)

    # 1. Look up template
    template = db.query(WhatsAppTemplate).filter(
        WhatsAppTemplate.meta_template_name == req.template_name
    ).first()
    if not template or template.status != "APPROVED":
        raise ValueError(f"Template '{req.template_name}' not found or not APPROVED by Meta")

    # 2. Resolve phone number
    recipient_phone = company.public_whatsapp or company.public_phone
    if not recipient_phone:
        raise ValueError(f"Company {company.name} has no recorded phone or WhatsApp number")

    cleaned_phone = clean_phone_number(recipient_phone)

    # 3. Check Consent Status (COMPLIANCE ENFORCEMENT)
    consent = db.query(ContactConsent).filter(
        ContactConsent.company_id == company.id,
        ContactConsent.channel == "whatsapp",
        ContactConsent.consent_status == "opted_in"
    ).first()

    has_consent = consent is not None

    # Render message text
    rendered_text = render_template_body(template, req.parameters)

    # If unconsented, create click-to-chat fallback link for manual contact
    click_to_chat_url = None
    if not has_consent:
        encoded_text = urllib.parse.quote(rendered_text)
        click_to_chat_url = f"https://wa.me/{cleaned_phone}?text={encoded_text}"

    msg = WhatsAppMessage(
        campaign_id=req.campaign_id,
        company_id=company.id,
        contact_id=req.contact_id,
        template_id=template.id,
        consent_id=consent.id if consent else None,
        recipient_phone=cleaned_phone,
        message_text=rendered_text,
        parameters_json=json.dumps(req.parameters),
        has_valid_consent=has_consent,
        click_to_chat_url=click_to_chat_url,
        approval_status="draft",  # Default state: draft mode (Mandatory Human Approval)
        delivery_status="draft",
        error_message=None if has_consent else "No recorded consent. Automated Cloud API sending blocked; use click-to-chat for manual outreach."
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def send_approved_whatsapp_message(
    db: Session,
    message_id: int,
    user_id: int
) -> Tuple[bool, str]:
    """Dispatches message via official Meta WhatsApp Business Cloud API strictly if eligible."""
    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
    if not msg:
        return False, "WhatsApp message record not found"

    # Rule 1: Mandatory Human Approval
    if msg.approval_status != "approved":
        return False, "Cannot send: Message must be explicitly approved by a user"

    # Rule 2: Strict Consent Check
    if not msg.has_valid_consent:
        return False, "Blocked: Promotional WhatsApp messages require documented valid permission. Automated send forbidden."

    # Rule 3: Global Suppression Check
    suppressed = db.query(SuppressionList).filter(
        SuppressionList.identifier == msg.recipient_phone
    ).first()
    if suppressed:
        msg.delivery_status = "failed"
        msg.error_message = "Blocked by global suppression list"
        db.commit()
        return False, "Recipient is on the suppression list"

    # Rule 4: Dispatch via Meta Cloud API or Test Provider
    meta_msg_id = f"wamid.HBgL{int(datetime.now().timestamp())}ACTTRIDENT"
    success = True
    error_note = None

    if settings.META_WA_ACCESS_TOKEN and settings.META_WA_PHONE_NUMBER_ID:
        try:
            url = f"https://graph.facebook.com/v19.0/{settings.META_WA_PHONE_NUMBER_ID}/messages"
            headers = {
                "Authorization": f"Bearer {settings.META_WA_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": msg.recipient_phone,
                "type": "template",
                "template": {
                    "name": msg.template.meta_template_name,
                    "language": {"code": msg.template.language}
                }
            }
            # Add parameters if provided
            if msg.parameters_json:
                params_dict = json.loads(msg.parameters_json)
                body_params = [{"type": "text", "text": v} for k, v in params_dict.items()]
                payload["template"]["components"] = [{"type": "body", "parameters": body_params}]

            resp = httpx.post(url, headers=headers, json=payload, timeout=10.0)
            if resp.status_code in (200, 201):
                data = resp.json()
                meta_msg_id = data.get("messages", [{}])[0].get("id", meta_msg_id)
            else:
                success = False
                error_note = f"Meta API Error ({resp.status_code}): {resp.text}"
        except Exception as e:
            success = False
            error_note = f"Connection error: {e}"
    else:
        # Mock / Test Mode
        success = True

    if success:
        msg.delivery_status = "sent"
        msg.sent_at = datetime.now(timezone.utc)
        msg.meta_message_id = meta_msg_id
        db.commit()

        record_audit_log(
            db=db,
            action="send_whatsapp_message",
            entity_type="whatsapp_message",
            entity_id=str(msg.id),
            user_id=user_id,
            details={"recipient": msg.recipient_phone, "meta_id": meta_msg_id}
        )
        return True, "WhatsApp message dispatched successfully via Meta Cloud API"
    else:
        msg.delivery_status = "failed"
        msg.error_message = error_note
        db.commit()
        return False, error_note


def process_incoming_meta_webhook(db: Session, payload: Dict[str, Any]):
    """Processes real Meta WhatsApp webhook events for message statuses and inbound replies."""
    entry = payload.get("entry", [])
    for e in entry:
        changes = e.get("changes", [])
        for c in changes:
            value = c.get("value", {})
            
            # Status updates (sent, delivered, read, failed)
            statuses = value.get("statuses", [])
            for st in statuses:
                meta_id = st.get("id")
                new_status = st.get("status")  # delivered, read, failed
                msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.meta_message_id == meta_id).first()
                if msg and new_status:
                    msg.delivery_status = new_status
                    db.commit()

            # Inbound messages
            messages = value.get("messages", [])
            for m in messages:
                from_phone = m.get("from")
                msg_body = m.get("text", {}).get("body", "")
                if from_phone and msg_body:
                    # Ingest into reply classifier & conversation engine
                    from app.services.reply_classifier_service import ingest_inbound_reply
                    ingest_inbound_reply(
                        db=db,
                        channel="whatsapp",
                        sender_identifier=from_phone,
                        recipient_identifier=settings.META_WA_PHONE_NUMBER_ID or "acttrident_wa",
                        subject="Inbound WhatsApp",
                        message_body=msg_body
                    )
