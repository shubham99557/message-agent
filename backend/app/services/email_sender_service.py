import email.utils
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
import httpx

from app.models.email import EmailDraft, EmailEvent, EmailSendAttempt
from app.models.activity import SuppressionList
from app.models.campaign import Campaign
from app.schemas.email import EmailSendResult
from app.core.config import settings
from app.core.audit import record_audit_log
from app.core.security import compute_content_hash
from app.integrations.gmail_adapter import (
    get_active_gmail_connection,
    send_gmail_message,
    GmailReauthRequiredError,
    GmailQuotaExceededError,
    GmailIntegrationError,
)


def check_daily_sending_limit(db: Session, campaign_id: Optional[int] = None) -> bool:
    """Enforces conservative daily email limits across campaigns and global ceiling."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Global daily sent count (strictly real sends, excluding simulated)
    global_sent_today = db.query(EmailDraft).filter(
        EmailDraft.sent_at >= today_start,
        EmailDraft.approval_status.in_(["sent", "delivered"])
    ).count()

    if global_sent_today >= settings.DEFAULT_DAILY_EMAIL_LIMIT:
        return False

    if campaign_id:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if campaign:
            camp_sent_today = db.query(EmailDraft).filter(
                EmailDraft.campaign_id == campaign_id,
                EmailDraft.sent_at >= today_start,
                EmailDraft.approval_status.in_(["sent", "delivered"])
            ).count()
            if camp_sent_today >= campaign.daily_email_limit:
                return False

    return True


def _ensure_opt_out_footer(draft: EmailDraft) -> str:
    """Attaches compliance opt-out footer if missing from draft text."""
    body = draft.body_text or ""
    if "opt-out" not in body.lower() and "unsubscribe" not in body.lower():
        footer = (
            f"\n\n---\n"
            f"ActTrident AI B2B Outreach • Targeting 5+ managed laptops in Siliguri, Gangtok, Patna & Bhagalpur.\n"
            f"To opt out of future communications regarding ActTrident evaluations, reply with 'Unsubscribe' "
            f"or visit https://acttrident.ai/opt-out?email={draft.recipient_email}"
        )
        return body + footer
    return body


def _next_attempt_number(db: Session, draft_id: int) -> int:
    return db.query(EmailSendAttempt).filter(EmailSendAttempt.draft_id == draft_id).count() + 1


def send_approved_email(
    db: Session,
    draft_id: int,
    user_id: int,
    http_client: Optional[httpx.Client] = None,
) -> EmailSendResult:
    """
    Dispatches an email draft strictly after validating:
    1. Explicit Human Approval
    2. Immutable SHA-256 Content Hash match
    3. Suppression List check
    4. Idempotency / duplicate-send protection
    5. Conservative daily sending limits
    6. Atomic approved -> sending state lock

    Records every send attempt separately from delivery outcomes.
    Never fabricates provider message IDs or marks mock sends as real deliveries.
    """
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return EmailSendResult(
            draft_id=draft_id,
            status="failed",
            provider=settings.EMAIL_PROVIDER,
            message="Email draft not found"
        )

    # 0. GLOBAL EMERGENCY KILL SWITCH & CAMPAIGN LIFECYCLE GUARD
    from app.services.orchestration_service import is_kill_switch_active, check_campaign_allows_dispatch

    ks_active, ks_reason = is_kill_switch_active(db)
    if ks_active:
        return EmailSendResult(
            draft_id=draft_id,
            status="blocked_kill_switch",
            provider=draft.provider,
            message=f"Blocked: Global Outbound Kill Switch is ACTIVE ({ks_reason})."
        )

    camp_ok, camp_err = check_campaign_allows_dispatch(db, draft.campaign_id)
    if not camp_ok:
        return EmailSendResult(
            draft_id=draft_id,
            status="blocked_campaign_inactive",
            provider=draft.provider,
            message=camp_err or "Campaign is paused or stopped."
        )

    # 1. IDEMPOTENCY GUARD: Prevent duplicate send if already dispatched with a provider ID
    if draft.approval_status in ("sent", "delivered") and draft.provider_message_id:
        return EmailSendResult(
            draft_id=draft_id,
            status="duplicate_blocked",
            provider=draft.provider,
            message=f"Idempotency Guard: Draft already dispatched (provider_message_id={draft.provider_message_id})."
        )

    # 2. MANDATORY HUMAN APPROVAL ENFORCEMENT
    if draft.approval_status != "approved":
        return EmailSendResult(
            draft_id=draft_id,
            status="failed",
            provider=draft.provider,
            message="Security Block: Email has not been approved by a designated reviewer"
        )

    # 3. IMMUTABLE CONTENT HASH VERIFICATION
    current_hash = compute_content_hash([draft.subject, draft.body_text])
    if not draft.approved_content_hash or current_hash != draft.approved_content_hash:
        draft.approval_status = "draft"
        draft.approved_by_id = None
        draft.approved_at = None
        draft.approved_content_hash = None
        db.commit()
        return EmailSendResult(
            draft_id=draft_id,
            status="failed",
            provider=draft.provider,
            message="Security Block: Draft content was modified after approval was granted. Re-approval required."
        )

    # Deterministic idempotency key for this approved version
    idem_key = f"email-draft-{draft.id}-v{draft.version or 1}-{current_hash[:16]}"
    prior_success = db.query(EmailSendAttempt).filter(
        EmailSendAttempt.idempotency_key == idem_key,
        EmailSendAttempt.outcome.in_(["sent", "smtp_accepted"])
    ).first()
    if prior_success:
        return EmailSendResult(
            draft_id=draft_id,
            status="duplicate_blocked",
            provider=prior_success.provider,
            message=f"Idempotency Guard: Approved draft version was already dispatched (attempt #{prior_success.attempt_number})."
        )

    # 4. SUPPRESSION LIST ENFORCEMENT
    suppressed = db.query(SuppressionList).filter(
        SuppressionList.identifier == draft.recipient_email.strip().lower()
    ).first()
    if suppressed:
        draft.approval_status = "rejected"
        draft.rejection_reason = f"Blocked by suppression list: {suppressed.reason}"
        db.commit()
        return EmailSendResult(
            draft_id=draft_id,
            status="blocked_suppression",
            provider=draft.provider,
            message=f"Recipient {draft.recipient_email} is on the global suppression list"
        )

    # 5. CONSERVATIVE DAILY LIMIT CHECK
    if not check_daily_sending_limit(db, draft.campaign_id):
        draft.approval_status = "queued"
        db.commit()
        return EmailSendResult(
            draft_id=draft_id,
            status="queued",
            provider=draft.provider,
            message=f"Daily email limit ({settings.DEFAULT_DAILY_EMAIL_LIMIT}) reached. Message held in queue."
        )

    # 6. ATOMIC DISPATCH LOCK (Prevents approval/sending race conditions & duplicate sends)
    claimed_rows = (
        db.query(EmailDraft)
        .filter(
            EmailDraft.id == draft_id,
            EmailDraft.approval_status == "approved",
            EmailDraft.approved_content_hash == current_hash
        )
        .update({"approval_status": "sending", "idempotency_key": idem_key}, synchronize_session="fetch")
    )
    db.commit()
    if claimed_rows == 0:
        return EmailSendResult(
            draft_id=draft_id,
            status="failed",
            provider=draft.provider,
            message="Race Condition Block: Draft is already sending, already sent, or modified concurrently."
        )
    db.refresh(draft)

    # 7. DETERMINE ACTIVE PROVIDER (Gmail OAuth2 > SMTP Fallback > Explicit Mock Simulation)
    body_with_optout = _ensure_opt_out_footer(draft)
    attempt_num = _next_attempt_number(db, draft.id)
    gmail_conn = get_active_gmail_connection(db)
    use_gmail = bool(
        gmail_conn
        and gmail_conn.status == "connected"
        and (gmail_conn.encrypted_access_token or gmail_conn.encrypted_refresh_token)
    )
    use_smtp = bool(
        not use_gmail
        and settings.EMAIL_PROVIDER == "smtp"
        and settings.SMTP_USER
        and settings.SMTP_PASSWORD
    )

    # --- PATH A: GMAIL API OAUTH 2.0 ---
    if use_gmail:
        draft.provider = "gmail"
        try:
            real_msg_id, real_thread_id = send_gmail_message(
                db=db,
                connection=gmail_conn,
                draft=draft,
                body_text=body_with_optout,
                http_client=http_client,
            )
            now_utc = datetime.now(timezone.utc)
            draft.approval_status = "sent"
            draft.sent_at = now_utc
            draft.provider_message_id = real_msg_id
            draft.provider_thread_id = real_thread_id
            draft.error_message = None

            db.add(EmailSendAttempt(
                draft_id=draft.id,
                attempt_number=attempt_num,
                idempotency_key=idem_key,
                provider="gmail",
                outcome="sent",
                provider_message_id=real_msg_id,
                provider_thread_id=real_thread_id,
                attempted_by_id=user_id,
            ))
            db.add(EmailEvent(
                draft_id=draft.id,
                event_type="sent",
                details=f"Accepted by Gmail API (id={real_msg_id}, threadId={real_thread_id})"
            ))
            if draft.company and draft.company.lead:
                draft.company.lead.pipeline_status = "contacted"
                draft.company.lead.last_contact_date = now_utc
            db.commit()

            record_audit_log(
                db=db,
                action="send_email_gmail",
                entity_type="email_draft",
                entity_id=str(draft.id),
                user_id=user_id,
                details={"recipient": draft.recipient_email, "provider_message_id": real_msg_id}
            )
            return EmailSendResult(
                draft_id=draft.id,
                status="sent",
                provider="gmail",
                message=f"Email sent via Gmail API (Message ID: {real_msg_id})"
            )
        except (GmailReauthRequiredError, GmailQuotaExceededError, GmailIntegrationError) as exc:
            draft.approval_status = "failed"
            draft.error_message = str(exc)
            db.add(EmailSendAttempt(
                draft_id=draft.id,
                attempt_number=attempt_num,
                idempotency_key=idem_key,
                provider="gmail",
                outcome=exc.error_code,
                error_code=exc.error_code,
                error_message=str(exc),
                attempted_by_id=user_id,
            ))
            db.add(EmailEvent(draft_id=draft.id, event_type="failed", details=f"Gmail error [{exc.error_code}]: {exc}"))
            db.commit()
            return EmailSendResult(
                draft_id=draft.id,
                status="failed",
                provider="gmail",
                message=str(exc)
            )

    # --- PATH B: CONFIGURED SMTP FALLBACK ---
    if use_smtp:
        draft.provider = "smtp"
        try:
            rfc_msg_id = email.utils.make_msgid(domain="acttrident.ai")
            msg = MIMEMultipart("alternative")
            msg["Subject"] = draft.subject
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = draft.recipient_email
            msg["Message-ID"] = rfc_msg_id
            msg["List-Unsubscribe"] = f"<https://acttrident.ai/opt-out?email={draft.recipient_email}>"

            msg.attach(MIMEText(body_with_optout, "plain", "utf-8"))
            msg.attach(MIMEText(draft.body_html or body_with_optout, "html", "utf-8"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, draft.recipient_email, msg.as_string())

            now_utc = datetime.now(timezone.utc)
            draft.approval_status = "sent"
            draft.sent_at = now_utc
            draft.provider_message_id = rfc_msg_id
            draft.error_message = None

            # Note: SMTP acceptance is NOT recipient inbox delivery!
            db.add(EmailSendAttempt(
                draft_id=draft.id,
                attempt_number=attempt_num,
                idempotency_key=idem_key,
                provider="smtp",
                outcome="smtp_accepted",
                provider_message_id=rfc_msg_id,
                attempted_by_id=user_id,
            ))
            db.add(EmailEvent(
                draft_id=draft.id,
                event_type="smtp_accepted",
                details=f"Accepted by SMTP relay {settings.SMTP_HOST} (Message-ID={rfc_msg_id}; recipient delivery not yet confirmed)"
            ))
            if draft.company and draft.company.lead:
                draft.company.lead.pipeline_status = "contacted"
                draft.company.lead.last_contact_date = now_utc
            db.commit()

            record_audit_log(
                db=db,
                action="send_email_smtp",
                entity_type="email_draft",
                entity_id=str(draft.id),
                user_id=user_id,
                details={"recipient": draft.recipient_email, "message_id": rfc_msg_id}
            )
            return EmailSendResult(
                draft_id=draft.id,
                status="sent",
                provider="smtp",
                message=f"Email accepted by SMTP relay (Message-ID: {rfc_msg_id}; delivery pending confirmation)"
            )
        except Exception as exc:
            draft.approval_status = "failed"
            draft.error_message = str(exc)
            db.add(EmailSendAttempt(
                draft_id=draft.id,
                attempt_number=attempt_num,
                idempotency_key=idem_key,
                provider="smtp",
                outcome="failed",
                error_code="smtp_error",
                error_message=str(exc),
                attempted_by_id=user_id,
            ))
            db.add(EmailEvent(draft_id=draft.id, event_type="failed", details=f"SMTP dispatch failure: {exc}"))
            db.commit()
            return EmailSendResult(
                draft_id=draft.id,
                status="failed",
                provider="smtp",
                message=f"SMTP dispatch failed: {exc}"
            )

    # --- PATH C: EXPLICIT MOCK / SIMULATION MODE ---
    # Must NEVER fabricate a real provider_message_id or report simulated sends as real 'sent'/'delivered'
    draft.provider = "mock"
    draft.approval_status = "simulated"
    draft.provider_message_id = None
    draft.error_message = None

    db.add(EmailSendAttempt(
        draft_id=draft.id,
        attempt_number=attempt_num,
        idempotency_key=idem_key,
        provider="mock",
        outcome="simulated",
        provider_message_id=None,
        attempted_by_id=user_id,
    ))
    db.add(EmailEvent(
        draft_id=draft.id,
        event_type="simulated",
        details="SIMULATION MODE: No external email was transmitted. Connect Gmail OAuth or SMTP to send live emails."
    ))
    db.commit()

    record_audit_log(
        db=db,
        action="simulate_email_send",
        entity_type="email_draft",
        entity_id=str(draft.id),
        user_id=user_id,
        details={"recipient": draft.recipient_email, "mode": "simulated"}
    )
    return EmailSendResult(
        draft_id=draft.id,
        status="simulated",
        provider="mock",
        message="SIMULATION MODE: Dispatch simulated locally (no external email sent; no provider ID fabricated)"
    )


def record_provider_email_event(
    db: Session,
    provider_message_id: str,
    event_type: str,
    details: Optional[str] = None
) -> Optional[EmailDraft]:
    """
    Records a provider-confirmed delivery, bounce, or complaint event.
    Only provider-confirmed events are allowed to transition a sent draft to 'delivered' or 'bounced'.
    """
    allowed_events = {"delivered", "bounced", "complaint", "opened", "clicked"}
    if event_type not in allowed_events:
        raise ValueError(f"Unsupported provider event_type '{event_type}'. Allowed: {sorted(allowed_events)}")

    draft = db.query(EmailDraft).filter(EmailDraft.provider_message_id == provider_message_id).first()
    if not draft:
        return None

    # Never mark simulated drafts as provider-delivered
    if draft.approval_status == "simulated":
        raise ValueError("Cannot record real provider delivery events for a simulated draft.")

    if event_type == "delivered" and draft.approval_status == "sent":
        draft.approval_status = "delivered"
    elif event_type in ("bounced", "complaint"):
        draft.approval_status = "bounced"
        draft.error_message = details or f"Provider reported {event_type}"

    db.add(EmailEvent(
        draft_id=draft.id,
        event_type=event_type,
        details=details or f"Provider-confirmed {event_type} event"
    ))
    db.commit()
    db.refresh(draft)
    return draft


def send_email(db: Session, draft: EmailDraft) -> EmailSendResult:
    """Convenience alias for background job worker dispatch."""
    return send_approved_email(db, draft.id, user_id=1)
