"""
Compliant LinkedIn Outreach Service.

Enforces:
- Official LinkedIn character limits (300 chars for connection notes, 1900 chars for direct messages)
- Global suppression list check
- SHA-256 tamper-evident content hashing
- Mandatory human approval (admin/manager) with immutable ApprovalRecord
- Automatic approval invalidation upon any edit to an approved draft
- Honest delivery states:
  * 'ready_for_manual_send' (compliant human-assisted handoff, provider_message_id=None) when Partner API is not approved
  * 'manually_sent_confirmed' once the human confirms sending inside LinkedIn
  * 'sent_via_api' ONLY when officially approved LinkedIn Partner Messaging API returns a genuine provider_message_id
"""
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.orm import Session

from app.core.audit import record_audit_log
from app.core.config import settings
from app.integrations.linkedin_adapter import (
    validate_linkedin_profile_url,
    get_active_linkedin_connection,
    dispatch_via_authorized_linkedin_partner_api,
    LinkedInIntegrationError,
)
from app.models.activity import SuppressionList
from app.models.company import Company
from app.models.email import ApprovalRecord
from app.models.linkedin import LinkedInMessage, LINKEDIN_MESSAGE_TYPES
from app.schemas.linkedin import LinkedInDraftCreate, LinkedInDraftUpdate


CHAR_LIMITS = {
    "connection_note": 300,
    "direct_message": 1900,
    "inmail_draft": 1900,
    "follow_up": 1900,
}


def compute_linkedin_content_hash(recipient_profile_url: str, message_type: str, message_body: str) -> str:
    raw = f"{recipient_profile_url.strip().lower()}|{message_type.strip().lower()}|{message_body.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_linkedin_suppressed(db: Session, company: Company, profile_url: str) -> bool:
    candidates = [profile_url.strip().lower()]
    if company.public_email:
        candidates.append(company.public_email.strip().lower())
    if company.public_phone:
        candidates.append(company.public_phone.strip().lower())
    existing = (
        db.query(SuppressionList)
        .filter(
            SuppressionList.identifier.in_(candidates),
            SuppressionList.channel.in_(["all", "linkedin"]),
        )
        .first()
    )
    return existing is not None


def _build_default_linkedin_copy(company: Company, message_type: str, recipient_name: Optional[str], custom_notes: Optional[str]) -> str:
    greeting_name = recipient_name or company.decision_maker_name or "there"
    city = company.city or "your region"
    if message_type == "connection_note":
        note = (
            f"Hi {greeting_name}, connecting from ActTrident. We help {city} IT & business teams protect "
            f"company laptops & browser workspaces and offer a 90-day free product evaluation for qualified teams (5+ devices). Would value connecting!"
        )
        return note[:295]
    extra = f"\n\nContext: {custom_notes.strip()}" if custom_notes else ""
    return (
        f"Hi {greeting_name},\n\n"
        f"I came across {company.name} in {city} and wanted to share a brief note about ActTrident. "
        f"We help teams with 5+ managed company laptops secure browser workflows and endpoint posture without slowing down staff.\n\n"
        f"We are currently offering a proposed 90-day free product evaluation for eligible teams in {city}. "
        f"If helpful, I would be glad to share a short overview or set up a quick 15-minute walkthrough.{extra}\n\n"
        f"Best regards,\nActTrident Business Development"
    )


def create_linkedin_draft(
    db: Session,
    draft_in: LinkedInDraftCreate,
    user_id: int,
) -> LinkedInMessage:
    if draft_in.message_type not in LINKEDIN_MESSAGE_TYPES:
        raise ValueError(f"Unsupported LinkedIn message_type '{draft_in.message_type}'. Valid: {LINKEDIN_MESSAGE_TYPES}")

    company = db.query(Company).filter(Company.id == draft_in.company_id).first()
    if not company:
        raise ValueError("Company not found.")

    profile_url = (draft_in.recipient_profile_url or company.linkedin_url or "").strip()
    valid_url, url_err = validate_linkedin_profile_url(profile_url)
    if not valid_url:
        raise ValueError(url_err)

    if is_linkedin_suppressed(db, company, profile_url):
        raise ValueError("Recipient is on the global suppression list. LinkedIn outreach is blocked.")

    recipient_name = draft_in.recipient_name or company.decision_maker_name
    body = (
        draft_in.custom_message.strip()
        if draft_in.custom_message and draft_in.custom_message.strip()
        else _build_default_linkedin_copy(company, draft_in.message_type, recipient_name, draft_in.custom_notes)
    )

    max_len = CHAR_LIMITS.get(draft_in.message_type, 1900)
    if len(body) > max_len:
        raise ValueError(
            f"LinkedIn '{draft_in.message_type}' exceeds character limit ({len(body)} > {max_len} chars)."
        )

    content_hash = compute_linkedin_content_hash(profile_url, draft_in.message_type, body)
    delivery_mode = (
        "authorized_partner_api"
        if (settings.LINKEDIN_MESSAGING_API_APPROVED and (settings.LINKEDIN_PARTNER_MESSAGING_ENDPOINT or "").strip())
        else "manual_handoff"
    )

    msg = LinkedInMessage(
        company_id=company.id,
        campaign_id=draft_in.campaign_id,
        recipient_name=recipient_name,
        recipient_profile_url=profile_url,
        message_type=draft_in.message_type,
        tone=draft_in.tone,
        message_body=body,
        content_hash=content_hash,
        approval_status="draft",
        delivery_mode=delivery_mode,
        created_by_user_id=user_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    record_audit_log(
        db=db,
        action="linkedin_draft_created",
        entity_type="linkedin_message",
        entity_id=str(msg.id),
        user_id=user_id,
        details={"company_id": company.id, "message_type": msg.message_type, "delivery_mode": delivery_mode},
    )
    return msg


def update_linkedin_draft(
    db: Session,
    message_id: int,
    updates: LinkedInDraftUpdate,
    user_id: int,
) -> LinkedInMessage:
    msg = db.query(LinkedInMessage).filter(LinkedInMessage.id == message_id).first()
    if not msg:
        raise ValueError("LinkedIn message not found.")
    if msg.approval_status in ("sent_via_api", "manually_sent_confirmed", "sending"):
        raise ValueError(f"Cannot edit LinkedIn message in final status '{msg.approval_status}'.")

    was_approved = msg.approval_status in ("approved", "ready_for_manual_send")

    if updates.recipient_profile_url is not None:
        valid_url, url_err = validate_linkedin_profile_url(updates.recipient_profile_url)
        if not valid_url:
            raise ValueError(url_err)
        msg.recipient_profile_url = updates.recipient_profile_url.strip()

    if updates.recipient_name is not None:
        msg.recipient_name = updates.recipient_name.strip() or None

    if updates.message_body is not None:
        new_body = updates.message_body.strip()
        if not new_body:
            raise ValueError("Message body cannot be empty.")
        max_len = CHAR_LIMITS.get(msg.message_type, 1900)
        if len(new_body) > max_len:
            raise ValueError(f"LinkedIn '{msg.message_type}' exceeds character limit ({len(new_body)} > {max_len} chars).")
        msg.message_body = new_body

    msg.content_hash = compute_linkedin_content_hash(msg.recipient_profile_url, msg.message_type, msg.message_body)

    # Editing an approved draft MUST invalidate approval!
    if was_approved:
        msg.approval_status = "draft"
        msg.approved_by_user_id = None
        msg.approved_at = None
        db.add(ApprovalRecord(
            entity_type="linkedin_message",
            entity_id=msg.id,
            approver_id=user_id,
            action="invalidated_by_edit",
            content_hash=msg.content_hash,
            reason="Draft content modified after approval",
            created_at=datetime.now(timezone.utc),
        ))

    db.commit()
    db.refresh(msg)
    record_audit_log(
        db=db,
        action="linkedin_draft_updated",
        entity_type="linkedin_message",
        entity_id=str(msg.id),
        user_id=user_id,
        details={"approval_invalidated": was_approved, "content_hash": msg.content_hash},
    )
    return msg


def approve_linkedin_message(db: Session, message_id: int, approver_user_id: int) -> LinkedInMessage:
    msg = db.query(LinkedInMessage).filter(LinkedInMessage.id == message_id).first()
    if not msg:
        raise ValueError("LinkedIn message not found.")
    if msg.approval_status not in ("draft", "rejected"):
        raise ValueError(f"Only 'draft' or 'rejected' LinkedIn messages can be approved (current: '{msg.approval_status}').")

    company = db.query(Company).filter(Company.id == msg.company_id).first()
    if company and is_linkedin_suppressed(db, company, msg.recipient_profile_url):
        raise ValueError("Recipient is on the suppression list; cannot approve.")

    now = datetime.now(timezone.utc)
    expected_hash = compute_linkedin_content_hash(msg.recipient_profile_url, msg.message_type, msg.message_body)
    msg.content_hash = expected_hash
    msg.approval_status = "approved"
    msg.approved_by_user_id = approver_user_id
    msg.approved_at = now
    msg.rejection_reason = None

    db.add(ApprovalRecord(
        entity_type="linkedin_message",
        entity_id=msg.id,
        approver_id=approver_user_id,
        action="approved",
        content_hash=expected_hash,
        created_at=now,
    ))
    db.commit()
    db.refresh(msg)
    record_audit_log(
        db=db,
        action="linkedin_message_approved",
        entity_type="linkedin_message",
        entity_id=str(msg.id),
        user_id=approver_user_id,
        details={"content_hash": expected_hash},
    )
    return msg


def reject_linkedin_message(db: Session, message_id: int, reviewer_user_id: int, reason: str) -> LinkedInMessage:
    msg = db.query(LinkedInMessage).filter(LinkedInMessage.id == message_id).first()
    if not msg:
        raise ValueError("LinkedIn message not found.")
    if msg.approval_status in ("sent_via_api", "manually_sent_confirmed"):
        raise ValueError("Cannot reject an already sent LinkedIn message.")

    now = datetime.now(timezone.utc)
    msg.approval_status = "rejected"
    msg.rejection_reason = reason.strip()
    msg.approved_by_user_id = None
    msg.approved_at = None

    db.add(ApprovalRecord(
        entity_type="linkedin_message",
        entity_id=msg.id,
        approver_id=reviewer_user_id,
        action="rejected",
        content_hash=msg.content_hash,
        reason=reason.strip(),
        created_at=now,
    ))
    db.commit()
    db.refresh(msg)
    return msg


def dispatch_approved_linkedin_message(
    db: Session,
    message_id: int,
    user_id: int,
    http_client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """
    Processes an approved LinkedIn message with strict truthfulness:
    1. Re-verifies content hash and suppression list.
    2. If LINKEDIN_MESSAGING_API_APPROVED is False -> transitions to 'ready_for_manual_send'
       (human-assisted handoff, provider_message_id=None — NEVER pretends an API send happened).
    3. If LINKEDIN_MESSAGING_API_APPROVED is True and OAuth connected -> dispatches via
       official authorized LinkedIn Partner API and stores the real provider_message_id.
    """
    msg = db.query(LinkedInMessage).filter(LinkedInMessage.id == message_id).first()
    if not msg:
        raise ValueError("LinkedIn message not found.")

    from app.services.orchestration_service import is_kill_switch_active, check_campaign_allows_dispatch

    ks_active, ks_reason = is_kill_switch_active(db)
    if ks_active:
        raise ValueError(f"Blocked: Global Outbound Kill Switch is ACTIVE ({ks_reason}).")

    camp_ok, camp_err = check_campaign_allows_dispatch(db, msg.campaign_id)
    if not camp_ok:
        raise ValueError(camp_err or "Campaign is paused or stopped.")
    if msg.approval_status != "approved":
        raise ValueError(
            f"LinkedIn message must be explicitly 'approved' before dispatch (current: '{msg.approval_status}')."
        )

    recomputed = compute_linkedin_content_hash(msg.recipient_profile_url, msg.message_type, msg.message_body)
    if recomputed != msg.content_hash:
        msg.approval_status = "draft"
        msg.approved_by_user_id = None
        msg.approved_at = None
        db.commit()
        raise ValueError("Content hash mismatch detected; approval invalidated.")

    company = db.query(Company).filter(Company.id == msg.company_id).first()
    if company and is_linkedin_suppressed(db, company, msg.recipient_profile_url):
        raise ValueError("Recipient is on the global suppression list. Dispatch blocked.")

    idempotency_key = msg.idempotency_key or f"li-msg-{msg.id}-{msg.content_hash[:12]}"
    msg.idempotency_key = idempotency_key

    partner_api_ready = bool(
        getattr(settings, "LIVE_SEND_ENABLED", False)
        and settings.LINKEDIN_MESSAGING_API_APPROVED
        and (settings.LINKEDIN_PARTNER_MESSAGING_ENDPOINT or "").strip()
    )

    if not partner_api_ready:
        msg.delivery_mode = "manual_handoff"
        msg.approval_status = "ready_for_manual_send"
        msg.provider_message_id = None  # Never fabricate an API ID!
        db.commit()
        db.refresh(msg)
        record_audit_log(
            db=db,
            action="linkedin_manual_handoff_prepared",
            entity_type="linkedin_message",
            entity_id=str(msg.id),
            user_id=user_id,
            details={"recipient_profile_url": msg.recipient_profile_url},
        )
        return {
            "id": msg.id,
            "status": "ready_for_manual_send",
            "delivery_mode": "manual_handoff",
            "provider_message_id": None,
            "recipient_profile_url": msg.recipient_profile_url,
            "message_body": msg.message_body,
            "instructions": (
                "Standard LinkedIn OAuth apps do not have automated 1:1 DM API access. "
                "Open the LinkedIn profile URL, paste the approved message manually, and click 'Confirm Manual Send' to log it to CRM."
            ),
        }

    # Authorized Partner API dispatch path
    conn = get_active_linkedin_connection(db)
    if not conn or conn.status != "connected":
        raise LinkedInIntegrationError("LinkedIn OAuth 2.0 must be connected before Partner API dispatch.", status_code=400)

    # Atomic conditional transition approved -> sending
    claimed = (
        db.query(LinkedInMessage)
        .filter(LinkedInMessage.id == msg.id, LinkedInMessage.approval_status == "approved")
        .update({"approval_status": "sending"}, synchronize_session=False)
    )
    db.commit()
    if claimed == 0:
        raise ValueError("LinkedIn message was already claimed or sent concurrently.")
    db.refresh(msg)

    try:
        api_res = dispatch_via_authorized_linkedin_partner_api(
            db=db,
            connection=conn,
            recipient_profile_url=msg.recipient_profile_url,
            message_type=msg.message_type,
            message_body=msg.message_body,
            idempotency_key=idempotency_key,
            http_client=http_client,
        )
        now = datetime.now(timezone.utc)
        msg.delivery_mode = "authorized_partner_api"
        msg.approval_status = "sent_via_api"
        msg.provider_message_id = api_res["provider_message_id"]
        msg.sent_at = now
        msg.sent_by_user_id = user_id
        msg.failure_reason = None
        if company and company.lead:
            company.lead.last_contact_date = now
            if company.lead.pipeline_status in ("discovered", "qualified", "approved_to_contact"):
                company.lead.pipeline_status = "contacted"
        db.commit()
        db.refresh(msg)
        record_audit_log(
            db=db,
            action="linkedin_sent_via_partner_api",
            entity_type="linkedin_message",
            entity_id=str(msg.id),
            user_id=user_id,
            details={"provider_message_id": msg.provider_message_id},
        )
        return {
            "id": msg.id,
            "status": "sent_via_api",
            "delivery_mode": "authorized_partner_api",
            "provider_message_id": msg.provider_message_id,
            "sent_at": msg.sent_at.isoformat(),
        }
    except Exception as exc:
        msg.approval_status = "failed"
        msg.failure_reason = str(exc)[:500]
        db.commit()
        raise


def confirm_linkedin_manual_send(
    db: Session,
    message_id: int,
    user_id: int,
    notes: Optional[str] = None,
) -> LinkedInMessage:
    """Marks a 'ready_for_manual_send' (or approved) message as manually sent by a human operator."""
    msg = db.query(LinkedInMessage).filter(LinkedInMessage.id == message_id).first()
    if not msg:
        raise ValueError("LinkedIn message not found.")
    if msg.approval_status not in ("ready_for_manual_send", "approved"):
        raise ValueError(
            f"Only 'ready_for_manual_send' or 'approved' messages can be confirmed as manually sent (current: '{msg.approval_status}')."
        )

    now = datetime.now(timezone.utc)
    msg.delivery_mode = "manual_handoff"
    msg.approval_status = "manually_sent_confirmed"
    msg.provider_message_id = None
    msg.sent_at = now
    msg.sent_by_user_id = user_id

    company = db.query(Company).filter(Company.id == msg.company_id).first()
    if company and company.lead:
        company.lead.last_contact_date = now
        if company.lead.pipeline_status in ("discovered", "qualified", "approved_to_contact"):
            company.lead.pipeline_status = "contacted"

    db.commit()
    db.refresh(msg)
    record_audit_log(
        db=db,
        action="linkedin_manual_send_confirmed",
        entity_type="linkedin_message",
        entity_id=str(msg.id),
        user_id=user_id,
        details={"recipient_profile_url": msg.recipient_profile_url, "notes": notes},
    )
    return msg


def list_linkedin_messages(db: Session, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    q = db.query(LinkedInMessage).order_by(LinkedInMessage.created_at.desc())
    if status_filter and status_filter != "all":
        q = q.filter(LinkedInMessage.approval_status == status_filter)
    rows = q.limit(100).all()
    out = []
    for m in rows:
        out.append({
            "id": m.id,
            "company_id": m.company_id,
            "campaign_id": m.campaign_id,
            "company_name": m.company.name if m.company else None,
            "recipient_name": m.recipient_name,
            "recipient_profile_url": m.recipient_profile_url,
            "message_type": m.message_type,
            "tone": m.tone,
            "message_body": m.message_body,
            "content_hash": m.content_hash,
            "approval_status": m.approval_status,
            "rejection_reason": m.rejection_reason,
            "approved_by_user_id": m.approved_by_user_id,
            "approved_at": m.approved_at,
            "delivery_mode": m.delivery_mode,
            "provider_message_id": m.provider_message_id,
            "sent_at": m.sent_at,
            "failure_reason": m.failure_reason,
            "created_at": m.created_at,
            "updated_at": m.updated_at,
        })
    return out
