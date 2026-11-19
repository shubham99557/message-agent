import re
import json
import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
import httpx
import hashlib
from sqlalchemy.orm import Session

from app.models.whatsapp import WhatsAppTemplate, WhatsAppMessage, WebhookEvent
from app.models.company import Company
from app.models.consent import ContactConsent
from app.models.activity import SuppressionList
from app.models.reply import Reply, Conversation
from app.schemas.whatsapp import WhatsAppDraftRequest, ContactConsentCreate
from app.core.config import settings
from app.core.audit import record_audit_log
from app.core.security import compute_content_hash, verify_meta_hmac_signature

logger = logging.getLogger(__name__)

# Pre-approved Meta WhatsApp Message Templates
DEFAULT_TEMPLATES = [
    {
        "meta_template_name": "acttrident_intro_utility_v1",
        "category": "UTILITY",
        "language": "en",
        "status": "APPROVED",
        "header_text": "ActTrident Technology Evaluation",
        "body_text": "Hello {{1}}, we noticed your organization manages active digital operations in {{2}}. ActTrident provides specialized workspace security for teams with 5+ laptops. Would you be open to a brief 15-minute product demonstration?",
        "footer_text": "Reply STOP to unsubscribe",
        "variables_schema": '{"1": "contact_name", "2": "city"}'
    },
    {
        "meta_template_name": "acttrident_intro_consultation",
        "category": "UTILITY",
        "language": "en",
        "status": "APPROVED",
        "header_text": "ActTrident Technology Evaluation",
        "body_text": "Hello {{1}}, we noticed {{2}} manages active digital infrastructure in {{3}}. ActTrident provides specialized workspace security for teams with 5+ laptops. Would you be open to a brief 15-minute product demonstration?",
        "footer_text": "Reply STOP to unsubscribe",
        "variables_schema": '{"1": "contact_name", "2": "company_name", "3": "city"}'
    },
    {
        "meta_template_name": "acttrident_demo_invite",
        "category": "UTILITY",
        "language": "en",
        "status": "APPROVED",
        "header_text": "Invitation: 90-Day Evaluation Program",
        "body_text": "Hi {{1}}, ActTrident is offering a 90-day evaluation program for eligible tech companies in {{2}}. We can demonstrate our browser security and device policy controls at your convenience.",
        "footer_text": "Reply STOP to unsubscribe",
        "variables_schema": '{"1": "contact_name", "2": "city"}'
    },
    {
        "meta_template_name": "acttrident_followup_formal",
        "category": "UTILITY",
        "language": "en",
        "status": "APPROVED",
        "header_text": "ActTrident Outreach Follow-Up",
        "body_text": "Hello {{1}}, following up regarding our proposed evaluation program for {{2}}. Please let us know if next Tuesday or Wednesday works for a demonstration.",
        "footer_text": "Reply STOP to unsubscribe",
        "variables_schema": '{"1": "contact_name", "2": "company_name"}'
    }
]


def seed_default_meta_templates(db: Session):
    for t in DEFAULT_TEMPLATES:
        existing = db.query(WhatsAppTemplate).filter(
            WhatsAppTemplate.meta_template_name == t["meta_template_name"]
        ).first()
        if not existing:
            tmpl = WhatsAppTemplate(**t)
            db.add(tmpl)
    db.commit()


def normalize_phone_number(phone: str) -> Optional[str]:
    """Cleans phone numbers into canonical E.164 without punctuation."""
    if not phone:
        return None
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if not cleaned.startswith("+"):
        if len(cleaned) == 10:
            cleaned = "+91" + cleaned
        else:
            cleaned = "+" + cleaned
    return cleaned


def record_contact_consent(db: Session, consent_in: ContactConsentCreate) -> ContactConsent:
    """Stores documented, verifiable consent prior to any promotional WhatsApp message."""
    raw_ident = getattr(consent_in, "contact_identifier", None)
    cleaned_phone = normalize_phone_number(raw_ident) if raw_ident else None
    proof_ref = getattr(consent_in, "proof_reference", None) or getattr(consent_in, "evidence_url", None)
    consent = ContactConsent(
        company_id=consent_in.company_id,
        contact_id=consent_in.contact_id,
        contact_identifier=cleaned_phone,
        channel=consent_in.channel,
        consent_status=consent_in.consent_status,
        consent_source=consent_in.consent_source,
        consent_purpose=consent_in.consent_purpose,
        proof_reference=proof_ref,
        evidence_url=proof_ref,
        notes=consent_in.notes
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


def verify_active_whatsapp_consent(db: Session, company_id: int, phone: str) -> Tuple[bool, Optional[ContactConsent]]:
    cleaned = normalize_phone_number(phone)
    consent = db.query(ContactConsent).filter(
        ContactConsent.company_id == company_id,
        ContactConsent.channel == "whatsapp",
        ContactConsent.consent_status == "opted_in"
    ).order_by(ContactConsent.consent_date.desc()).first()

    if consent:
        return True, consent

    if cleaned:
        consent_by_phone = db.query(ContactConsent).filter(
            ContactConsent.contact_identifier == cleaned,
            ContactConsent.channel == "whatsapp",
            ContactConsent.consent_status == "opted_in"
        ).order_by(ContactConsent.consent_date.desc()).first()
        if consent_by_phone:
            return True, consent_by_phone

    return False, None


def render_template_body(template: WhatsAppTemplate, parameters: Dict[str, str]) -> str:
    text = template.body_text
    for key, val in parameters.items():
        text = text.replace(f"{{{{{key}}}}}", str(val))
    return text


def create_whatsapp_message(
    db: Session,
    company: Company,
    req: WhatsAppDraftRequest
) -> WhatsAppMessage:
    template = None
    if getattr(req, "template_id", None):
        template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == req.template_id).first()
    elif getattr(req, "template_name", None):
        template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.meta_template_name == req.template_name).first()
        if not template:
            seed_default_meta_templates(db)
            template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.meta_template_name == req.template_name).first()
    else:
        seed_default_meta_templates(db)
        template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.status == "APPROVED").first()

    if not template or template.status != "APPROVED":
        raise ValueError("Selected WhatsApp Template not found or not approved")

    phone_to_use = req.recipient_phone or company.public_whatsapp or company.public_phone
    if not phone_to_use:
        raise ValueError("Company does not have a public WhatsApp or telephone number")

    cleaned_phone = normalize_phone_number(phone_to_use)
    has_consent, consent = verify_active_whatsapp_consent(db, company.id, cleaned_phone)
    rendered_text = render_template_body(template, req.parameters)

    click_to_chat_url = None
    if not has_consent:
        encoded_text = urllib.parse.quote(rendered_text)
        wa_digits = cleaned_phone.lstrip("+")
        click_to_chat_url = f"https://wa.me/{wa_digits}?text={encoded_text}"

    content_hash = compute_content_hash([rendered_text])

    msg = WhatsAppMessage(
        campaign_id=req.campaign_id,
        company_id=company.id,
        contact_id=req.contact_id,
        template_id=template.id,
        consent_id=consent.id if consent else None,
        recipient_phone=cleaned_phone,
        message_text=rendered_text,
        parameters_json=json.dumps(req.parameters),
        content_hash=content_hash,
        version=1,
        has_valid_consent=has_consent,
        click_to_chat_url=click_to_chat_url,
        approval_status="draft",
        delivery_status="draft",
        error_message=None if has_consent else "No recorded consent. Automated Cloud API sending blocked; use click-to-chat for manual outreach."
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def approve_whatsapp_message_internal(db: Session, msg: WhatsAppMessage, user_id: int) -> WhatsAppMessage:
    from app.models.email import ApprovalRecord

    # Re-verify live consent at approval time
    has_consent, consent_rec = verify_active_whatsapp_consent(db, msg.company_id, msg.recipient_phone)
    if not has_consent:
        msg.has_valid_consent = False
        db.commit()
        raise ValueError("Unsolicited WhatsApp outreach is forbidden. Documented consent is mandatory before approval.")

    current_hash = compute_content_hash([msg.message_text])
    msg.has_valid_consent = True
    msg.consent_id = consent_rec.id if consent_rec else msg.consent_id
    msg.content_hash = current_hash
    msg.approved_content_hash = current_hash
    msg.approval_status = "approved"
    msg.approved_by_id = user_id
    msg.approved_at = datetime.now(timezone.utc)

    db.add(ApprovalRecord(
        entity_type="whatsapp_message",
        entity_id=msg.id,
        approver_id=user_id,
        action="approved",
        content_version=msg.version or 1,
        content_hash=current_hash,
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()
    db.refresh(msg)
    return msg


def check_daily_whatsapp_limit(db: Session, campaign_id: Optional[int] = None) -> bool:
    """Enforces conservative daily WhatsApp limits across campaigns and global ceiling."""
    from app.models.campaign import Campaign

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    global_sent_today = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.sent_at >= today_start,
        WhatsAppMessage.approval_status == "sent",
    ).count()
    if global_sent_today >= settings.DEFAULT_DAILY_WHATSAPP_LIMIT:
        return False

    if campaign_id:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if campaign and campaign.daily_whatsapp_limit:
            camp_sent_today = db.query(WhatsAppMessage).filter(
                WhatsAppMessage.campaign_id == campaign_id,
                WhatsAppMessage.sent_at >= today_start,
                WhatsAppMessage.approval_status == "sent",
            ).count()
            if camp_sent_today >= campaign.daily_whatsapp_limit:
                return False
    return True


def send_approved_whatsapp_message(
    db: Session,
    message_id: int,
    user_id: int,
    http_client: Optional[httpx.Client] = None,
) -> Tuple[bool, str]:
    """
    Dispatches a WhatsApp template message strictly after validating:
    1. Idempotency (already sent with wamid)
    2. Explicit Human Approval
    3. Immutable SHA-256 Content Hash
    4. LIVE re-verification of documented opt-in consent immediately before dispatch
    5. Global suppression list check
    6. Atomic approved -> sending state lock
    7. Template approval status & numerically ordered parameters (via Meta adapter)
    """
    from app.integrations.whatsapp_adapter import (
        is_meta_wa_configured,
        send_meta_template_message,
        validate_and_order_template_parameters,
        MetaWhatsAppError,
    )

    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
    if not msg:
        return False, "WhatsApp message record not found"

    # Rule 0: Global Emergency Kill Switch & Campaign Pause/Stop Guard
    from app.services.orchestration_service import is_kill_switch_active, check_campaign_allows_dispatch

    ks_active, ks_reason = is_kill_switch_active(db)
    if ks_active:
        return False, f"Blocked: Global Outbound Kill Switch is ACTIVE ({ks_reason})."

    camp_ok, camp_err = check_campaign_allows_dispatch(db, msg.campaign_id)
    if not camp_ok:
        return False, camp_err or "Campaign is paused or stopped."

    # Idempotency guard: prevent duplicate dispatch
    if msg.approval_status == "sent" and msg.meta_message_id:
        return False, f"Idempotency Guard: WhatsApp message already dispatched (meta_message_id={msg.meta_message_id})."

    # Rule 1: Mandatory Human Approval
    if msg.approval_status != "approved":
        return False, "Cannot send: Message must be explicitly approved by a designated reviewer"

    # Rule 2: Content Hash Immutability
    current_hash = compute_content_hash([msg.message_text])
    if not msg.approved_content_hash or current_hash != msg.approved_content_hash:
        msg.approval_status = "draft"
        msg.approved_by_id = None
        msg.approved_at = None
        msg.approved_content_hash = None
        db.commit()
        return False, "Security Block: Message content changed after approval. Re-approval required."

    # Rule 3: LIVE Consent Re-Check immediately before dispatch (catches post-draft opt-outs)
    live_consent, _ = verify_active_whatsapp_consent(db, msg.company_id, msg.recipient_phone)
    if not live_consent:
        msg.has_valid_consent = False
        msg.delivery_status = "failed"
        msg.error_message = "Blocked: Consent revoked or no valid documented WhatsApp opt-in exists."
        db.commit()
        return False, "Blocked: Promotional WhatsApp messages require active documented permission. Automated send forbidden."

    # Rule 4: Global Suppression Check
    clean_phone = normalize_phone_number(msg.recipient_phone) or msg.recipient_phone
    suppressed = db.query(SuppressionList).filter(
        (SuppressionList.identifier == msg.recipient_phone) | (SuppressionList.identifier == clean_phone)
    ).first()
    if suppressed:
        msg.delivery_status = "failed"
        msg.error_message = f"Blocked by global suppression list: {suppressed.reason}"
        db.commit()
        return False, "Recipient is on the suppression list"

    # Rule 5: Validate template approval & parameter ordering before claiming lock
    if msg.template:
        params_dict = json.loads(msg.parameters_json) if msg.parameters_json else {}
        try:
            validate_and_order_template_parameters(msg.template, params_dict, require_meta_approved=True)
        except MetaWhatsAppError as exc:
            msg.delivery_status = "failed"
            msg.error_message = str(exc)
            db.commit()
            return False, str(exc)

    # Rule 5b: Conservative Daily & Per-Minute WhatsApp Rate Limits
    if not check_daily_whatsapp_limit(db, msg.campaign_id):
        return False, f"Daily WhatsApp sending limit ({settings.DEFAULT_DAILY_WHATSAPP_LIMIT}) reached. Message held."

    from app.services.job_service import check_rate_limit
    wa_per_min = getattr(settings, "OUTBOUND_RATE_LIMIT_WA_PER_MIN", 10)
    if not check_rate_limit("whatsapp_dispatch", wa_per_min, 60):
        return False, f"Per-minute WhatsApp rate limit ({wa_per_min}/min) reached. Please retry shortly."

    # Rule 6: Atomic dispatch lock (prevents race-condition duplicate sends)
    idem_key = f"wa-msg-{msg.id}-v{msg.version or 1}-{current_hash[:16]}"
    claimed = (
        db.query(WhatsAppMessage)
        .filter(
            WhatsAppMessage.id == message_id,
            WhatsAppMessage.approval_status == "approved",
            WhatsAppMessage.approved_content_hash == current_hash,
        )
        .update({"approval_status": "sending", "delivery_status": "sending", "idempotency_key": idem_key}, synchronize_session="fetch")
    )
    db.commit()
    if claimed == 0:
        return False, "Race Condition Block: Message is already sending, already sent, or modified concurrently."
    db.refresh(msg)

    # Rule 7: Dispatch via Official Meta Cloud API or Explicit Simulation Mode
    live_send_permitted = getattr(settings, "LIVE_SEND_ENABLED", False)
    if live_send_permitted and is_meta_wa_configured():
        try:
            meta_msg_id = send_meta_template_message(db=db, msg=msg, http_client=http_client)
            now_utc = datetime.now(timezone.utc)
            msg.approval_status = "sent"
            msg.delivery_status = "sent"
            msg.sent_at = now_utc
            msg.meta_message_id = meta_msg_id
            msg.error_message = None
            db.commit()

            record_audit_log(
                db=db,
                action="send_whatsapp_message",
                entity_type="whatsapp_message",
                entity_id=str(msg.id),
                user_id=user_id,
                details={"recipient": msg.recipient_phone, "meta_id": meta_msg_id},
            )
            return True, f"WhatsApp message dispatched via Meta Cloud API (Message ID: {meta_msg_id})"
        except MetaWhatsAppError as exc:
            msg.approval_status = "failed"
            msg.delivery_status = "failed"
            msg.error_message = str(exc)
            db.commit()
            return False, str(exc)
        except Exception as exc:
            msg.approval_status = "failed"
            msg.delivery_status = "failed"
            msg.error_message = f"Connection error: {exc}"
            db.commit()
            return False, str(exc)
    else:
        # Mock / Simulation Mode: NEVER report simulated messages as real 'sent'/'delivered' and NEVER fabricate wamid
        msg.approval_status = "simulated"
        msg.delivery_status = "simulated"
        msg.meta_message_id = None
        msg.error_message = None
        db.commit()
        record_audit_log(
            db=db,
            action="simulate_whatsapp_send",
            entity_type="whatsapp_message",
            entity_id=str(msg.id),
            user_id=user_id,
            details={"recipient": msg.recipient_phone, "mode": "simulated"},
        )
        return True, "SIMULATION MODE: WhatsApp dispatch simulated locally (no live Meta Cloud API message sent)"


def process_incoming_meta_webhook(
    db: Session,
    raw_body: bytes,
    payload: Dict[str, Any],
    signature_header: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Processes Meta WhatsApp webhook with:
    1. HMAC-SHA256 signature verification using META_APP_SECRET
    2. Idempotent webhook event persistence & deduplication
    3. Delivery/read/failed status updates with error reason extraction
    4. Inbound reply classification, STOP opt-out enforcement, and per-message deduplication
    """
    from app.services.reply_classifier_service import ingest_inbound_reply

    # 1. HMAC Signature Verification
    if settings.META_APP_SECRET:
        if not verify_meta_hmac_signature(raw_body, signature_header, settings.META_APP_SECRET):
            logger.warning("Rejected forged or invalid Meta webhook signature.")
            return False, "Invalid signature"
    elif settings.ENVIRONMENT.lower() == "production":
        logger.error("META_APP_SECRET is required in production for webhook verification.")
        return False, "Webhook secret not configured"

    # 2. Idempotency Check & Event Persistence
    idempotency_key = hashlib.sha256(raw_body).hexdigest()
    existing_event = db.query(WebhookEvent).filter(WebhookEvent.idempotency_key == idempotency_key).first()
    if existing_event:
        logger.info(f"Duplicate webhook ignored (idempotency_key={idempotency_key[:12]}).")
        return True, "Duplicate event skipped"

    event_record = WebhookEvent(
        source="meta_whatsapp",
        idempotency_key=idempotency_key,
        payload_json=json.dumps(payload),
        status="received"
    )
    db.add(event_record)
    db.commit()
    db.refresh(event_record)

    try:
        entry = payload.get("entry", [])
        for e in entry:
            changes = e.get("changes", [])
            for c in changes:
                value = c.get("value", {})

                # Status updates (sent, delivered, read, failed)
                statuses = value.get("statuses", [])
                for s in statuses:
                    meta_id = s.get("id")
                    status_name = (s.get("status") or "").lower()
                    if not meta_id or not status_name:
                        continue
                    wa_msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.meta_message_id == meta_id).first()
                    if wa_msg and wa_msg.delivery_status != "simulated":
                        wa_msg.delivery_status = status_name
                        if status_name == "failed":
                            errs = s.get("errors") or []
                            if errs:
                                first_err = errs[0]
                                wa_msg.error_message = f"Meta delivery error {first_err.get('code', '')}: {first_err.get('title', '')} {first_err.get('message', '')}".strip()
                        db.commit()

                # Inbound replies
                messages = value.get("messages", [])
                display_num = (value.get("metadata") or {}).get("display_phone_number", "ActTrident WA")
                for m in messages:
                    wamid = m.get("id")
                    if wamid and db.query(Reply).filter(Reply.provider_message_id == wamid).first():
                        continue  # Duplicate inbound message

                    sender = m.get("from", "")
                    text_body = (m.get("text") or {}).get("body", "") or (m.get("button") or {}).get("text", "")
                    cleaned_sender = normalize_phone_number(sender) or sender

                    reply = ingest_inbound_reply(
                        db=db,
                        channel="whatsapp",
                        sender_identifier=cleaned_sender,
                        recipient_identifier=display_num,
                        subject="WhatsApp Inbound Message",
                        message_body=text_body,
                    )
                    if wamid:
                        reply.provider_message_id = wamid
                        db.commit()

        event_record.status = "processed"
        event_record.processed_at = datetime.now(timezone.utc)
        db.commit()
        return True, "Processed"
    except Exception as e:
        event_record.status = "failed"
        event_record.error_message = str(e)
        db.commit()
        return False, str(e)
