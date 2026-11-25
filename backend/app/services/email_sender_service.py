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
from app.core.security import compute_content_hash, compute_draft_approval_hash, verify_draft_approval
from app.integrations.gmail_adapter import (
    get_active_gmail_connection,
    send_gmail_message,
    GmailReauthRequiredError,
    GmailQuotaExceededError,
    GmailIntegrationError,
)


def get_mailbox_warmup_limit(db: Session) -> int:
    """
    Computes recommended maximum daily outreach limit according to mailbox warm-up schedule:
    - Days 1-7: max 20 emails/day
    - Days 8-14: max 50 emails/day
    - Days 15-21: max 100 emails/day
    - Days 22+: max 200 emails/day (hard ceiling for cold B2B outreach reputation protection)
    """
    first_send = db.query(EmailDraft.sent_at).filter(
        EmailDraft.approval_status.in_(["sent", "delivered"]),
        EmailDraft.sent_at.isnot(None)
    ).order_by(EmailDraft.sent_at.asc()).first()

    if not first_send or not first_send[0]:
        return 20  # Brand new mailbox

    earliest = first_send[0]
    if earliest.tzinfo is None:
        earliest = earliest.replace(tzinfo=timezone.utc)
    days_active = max(1, (datetime.now(timezone.utc) - earliest).days + 1)

    if days_active <= 7:
        return 20
    elif days_active <= 14:
        return 50
    elif days_active <= 21:
        return 100
    else:
        return min(200, settings.DEFAULT_DAILY_EMAIL_LIMIT)


def check_daily_sending_limit(db: Session, campaign_id: Optional[int] = None) -> bool:
    """Enforces conservative daily email limits across campaigns, warm-up schedules, and global ceiling."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Global daily sent count (strictly real sends, excluding simulated)
    global_sent_today = db.query(EmailDraft).filter(
        EmailDraft.sent_at >= today_start,
        EmailDraft.approval_status.in_(["sent", "delivered"])
    ).count()

    warmup_cap = get_mailbox_warmup_limit(db)
    effective_limit = min(settings.DEFAULT_DAILY_EMAIL_LIMIT, warmup_cap)
    if global_sent_today >= effective_limit:
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
    if "opt-out" not in body.lower() and "unsubscribe" not in body.lower() and "prefer not to receive" not in body.lower():
        footer = (
            f"\n\n---\n"
            f"If you would prefer not to receive further business emails from us, please reply and let us know."
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

    # 3. IMMUTABLE CONTENT HASH VERIFICATION (7-FACTOR INTEGRITY CHECK)
    is_valid = verify_draft_approval(
        stored_signature=draft.approved_content_hash,
        company_id=draft.company_id,
        recipient=draft.recipient_email,
        channel="email",
        subject=draft.subject,
        body_text=draft.body_text,
        version=draft.version or 1,
        approved_by_id=draft.approved_by_id,
        approved_at=draft.approved_at,
        allow_legacy=True
    )

    if not is_valid:
        draft.approval_status = "draft"
        draft.approved_by_id = None
        draft.approved_at = None
        draft.approved_content_hash = None
        db.commit()
        return EmailSendResult(
            draft_id=draft_id,
            status="failed",
            provider=draft.provider,
            message="Security Block: Draft content was modified or approval metadata was altered after approval was granted. Re-approval required."
        )

    current_hash = draft.approved_content_hash or ""

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

    # 4. RECIPIENT VALIDATION & SUPPRESSION LIST ENFORCEMENT
    if not draft.recipient_email or not draft.recipient_email.strip():
        return EmailSendResult(
            draft_id=draft_id,
            status="failed",
            provider=draft.provider,
            message="Security Block: Email has no recipient email address (missing_recipient)"
        )

    clean_recipient = draft.recipient_email.strip().lower()
    suppressed = db.query(SuppressionList).filter(
        SuppressionList.identifier == clean_recipient
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

    # 5. CONSERVATIVE DAILY LIMIT & PER-MINUTE RATE LIMIT CHECKS
    if not check_daily_sending_limit(db, draft.campaign_id):
        draft.approval_status = "queued"
        db.commit()
        return EmailSendResult(
            draft_id=draft_id,
            status="queued",
            provider=draft.provider,
            message=f"Daily email limit ({settings.DEFAULT_DAILY_EMAIL_LIMIT}) reached. Message held in queue."
        )

    from app.services.job_service import check_rate_limit
    email_per_min = getattr(settings, "OUTBOUND_RATE_LIMIT_EMAIL_PER_MIN", 30)
    if not check_rate_limit("email_dispatch", email_per_min, 60):
        return EmailSendResult(
            draft_id=draft_id,
            status="rate_limited",
            provider=draft.provider,
            message=f"Per-minute email rate limit ({email_per_min}/min) reached. Please retry shortly."
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

    # LIVE OUTREACH SAFETY GATE:
    # LIVE_SEND_ENABLED must be explicitly True to dispatch live external network requests.
    # When False (the secure default), missing or present credentials fail closed to local simulation.
    live_send_permitted = getattr(settings, "LIVE_SEND_ENABLED", False)

    use_gmail = bool(
        live_send_permitted
        and gmail_conn
        and gmail_conn.status == "connected"
        and (gmail_conn.encrypted_access_token or gmail_conn.encrypted_refresh_token)
    )
    use_smtp = bool(
        live_send_permitted
        and not use_gmail
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
        if draft.company and draft.company.lead:
            draft.company.lead.pipeline_status = "bounced"

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


# ---------------------------------------------------------------------------
# PHASE 4A: TEST-MODE PROVIDER DISPATCH & AUTHENTICATED WEBHOOK PROCESSING
# ---------------------------------------------------------------------------

RESEND_TEST_RECIPIENTS = {
    "delivered@resend.dev",
    "bounced@resend.dev",
    "complained@resend.dev",
}


def _get_test_allowlist() -> set:
    raw = getattr(settings, "EMAIL_TEST_ALLOWLIST", "") or ""
    operator_set = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return operator_set | RESEND_TEST_RECIPIENTS


def _is_real_crm_prospect_email(db: Session, email_addr: str) -> bool:
    """Returns True if email_addr belongs to any non-demo CRM prospect or contact."""
    from app.models.company import Company, CompanyContact
    clean = email_addr.strip().lower()
    comp = db.query(Company).filter(
        Company.is_demo == False,  # noqa: E712
        (Company.public_email.ilike(clean)) | (Company.decision_maker_email.ilike(clean))
    ).first()
    if comp:
        return True
    contact = (
        db.query(CompanyContact)
        .join(Company, CompanyContact.company_id == Company.id)
        .filter(Company.is_demo == False, CompanyContact.email.ilike(clean))  # noqa: E712
        .first()
    )
    return contact is not None


def send_test_mode_email(
    db: Session,
    recipient_email: str,
    subject: str,
    body_text: str,
    user_id: int,
    idempotency_key: str,
    provider_override: Optional[str] = None,
    http_client: Optional[httpx.Client] = None,
) -> dict:
    """
    Phase 4A Independent Test-Mode Safety Gate.
    Allows sending ONLY to operator-controlled EMAIL_TEST_ALLOWLIST addresses while
    LIVE_SEND_ENABLED remains False. Never dispatches to real CRM prospect addresses.
    """
    import logging
    from app.core.security import validate_recipient_email_syntax
    from app.integrations.email_provider_adapter import (
        EmailProviderSendRequest,
        get_sandbox_email_provider,
    )
    from app.services.unsubscribe_service import build_unsubscribe_headers

    tlog = logging.getLogger("acttrident.email_test_mode")

    if not getattr(settings, "EMAIL_TEST_MODE_ENABLED", False):
        raise PermissionError("Test-mode email dispatch is disabled (EMAIL_TEST_MODE_ENABLED=false).")

    clean_recipient = validate_recipient_email_syntax(recipient_email).lower()
    allowlist = _get_test_allowlist()
    if not allowlist or clean_recipient not in allowlist:
        raise PermissionError(
            f"Test-mode safety block: '{clean_recipient}' is not in EMAIL_TEST_ALLOWLIST."
        )

    if _is_real_crm_prospect_email(db, clean_recipient):
        raise PermissionError(
            f"Test-mode safety block: '{clean_recipient}' belongs to a real CRM prospect and cannot be used for test dispatch."
        )

    suppressed = db.query(SuppressionList).filter(SuppressionList.identifier == clean_recipient).first()
    if suppressed:
        raise ValueError(f"Recipient '{clean_recipient}' is on the suppression list ({suppressed.reason}).")

    # Idempotency check via AuditLog for test-mode dispatches
    from app.models.activity import AuditLog
    clean_idem = f"testmode-{idempotency_key.strip()}"
    prior_logs = db.query(AuditLog).filter(AuditLog.action == "send_test_mode_email").order_by(AuditLog.id.desc()).limit(100).all()
    for log_row in prior_logs:
        if log_row.details and clean_idem in log_row.details and '"outcome": "accepted"' in log_row.details:
            return {
                "status": "duplicate_blocked",
                "idempotent": True,
                "provider": getattr(settings, "EMAIL_SANDBOX_PROVIDER", "sandbox_mock"),
                "provider_message_id": log_row.entity_id,
                "message": "Duplicate test-mode send prevented by idempotency key.",
            }

    unsub_headers, _ = build_unsubscribe_headers(clean_recipient, company_id=None)
    footer = "\n\n---\nIf you would prefer not to receive further business emails from us, please reply and let us know."
    full_body = body_text.strip() + ("" if "prefer not to receive" in body_text.lower() else footer)
    full_html = f"<p>{full_body.replace(chr(10), '<br/>')}</p>"

    adapter = get_sandbox_email_provider(provider_override=provider_override, http_client=http_client)
    from_email = (
        getattr(settings, "RESEND_FROM_EMAIL", "onboarding@resend.dev") or "onboarding@resend.dev"
        if adapter.provider_name == "resend"
        else settings.SMTP_FROM_EMAIL
    )
    req = EmailProviderSendRequest(
        recipient_email=clean_recipient,
        subject=subject,
        body_text=full_body,
        body_html=full_html,
        from_name=settings.SMTP_FROM_NAME,
        from_email=from_email,
        idempotency_key=clean_idem,
        headers=unsub_headers,
        is_test_mode=True,
    )
    res = adapter.send_test_email(req)

    # Never log message body or API secrets
    tlog.info(
        f"Test-mode dispatch outcome={res.outcome} provider={res.provider} "
        f"provider_message_id={res.provider_message_id} attempts={res.attempts_made}"
    )

    record_audit_log(
        db=db,
        action="send_test_mode_email",
        entity_type="email_test_mode",
        entity_id=res.provider_message_id or clean_idem,
        user_id=user_id,
        details={
            "idempotency_key": clean_idem,
            "recipient": clean_recipient,
            "provider": res.provider,
            "outcome": res.outcome,
            "is_sandbox": res.is_sandbox,
            "attempts_made": res.attempts_made,
            "live_send_enabled": settings.LIVE_SEND_ENABLED,
        },
    )

    return {
        "status": res.outcome,
        "provider": res.provider,
        "is_sandbox": res.is_sandbox,
        "provider_message_id": res.provider_message_id,
        "attempts_made": res.attempts_made,
        "error_code": res.error_code,
        "error_message": res.error_message,
        "unsubscribe_headers_attached": True,
        "live_send_enabled": settings.LIVE_SEND_ENABLED,
    }


def verify_email_webhook_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    timestamp_header: Optional[str] = None,
) -> None:
    """
    Verifies HMAC-SHA256 provider webhook signature in constant time and enforces
    optional timestamp replay window (<= 300s). Raises PermissionError on failure.
    """
    import hashlib
    import hmac

    secret = (getattr(settings, "EMAIL_WEBHOOK_SECRET", "") or "").strip()
    if not secret:
        raise PermissionError("Webhook rejected: EMAIL_WEBHOOK_SECRET is not configured.")
    if not signature_header or not signature_header.strip():
        raise PermissionError("Webhook rejected: missing signature header.")

    if timestamp_header is not None:
        try:
            ts = int(str(timestamp_header).strip())
        except ValueError as exc:
            raise PermissionError("Webhook rejected: malformed timestamp header.") from exc
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if abs(now_ts - ts) > 300:
            raise PermissionError("Webhook rejected: timestamp outside 300s replay window.")

    provided = signature_header.strip()
    if provided.startswith("sha256="):
        provided = provided.split("=", 1)[1]

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, provided):
        raise PermissionError("Webhook rejected: invalid HMAC signature.")


def process_provider_webhook_event(
    db: Session,
    raw_body: bytes,
    signature_header: Optional[str],
    timestamp_header: Optional[str],
    payload: dict,
) -> dict:
    """
    Authenticated provider webhook processor with signature check, replay protection,
    idempotent event deduplication, and hard-bounce/complaint vs soft-bounce separation.
    """
    from app.models.whatsapp import WebhookEvent

    verify_email_webhook_signature(raw_body, signature_header, timestamp_header)

    event_id = str(payload.get("event_id") or "").strip()
    event_type = str(payload.get("event_type") or "").strip().lower()
    provider_message_id = str(payload.get("provider_message_id") or "").strip()
    recipient = str(payload.get("recipient") or "").strip().lower()
    details = str(payload.get("details") or "")

    if not event_id or not event_type:
        raise ValueError("Webhook payload must include 'event_id' and 'event_type'.")

    # Idempotent duplicate event check
    dup = db.query(WebhookEvent).filter(
        WebhookEvent.source == "email_provider",
        WebhookEvent.event_id == event_id,
    ).first()
    if dup:
        return {"status": "duplicate_ignored", "event_id": event_id, "idempotent": True}

    db.add(WebhookEvent(
        source="email_provider",
        event_id=event_id,
        idempotency_key=f"email-wh-{event_id}",
        payload_json=raw_body.decode("utf-8", errors="replace")[:2000],
        status="processed",
    ))

    allowed_types = {"accepted", "delivered", "hard_bounce", "bounced", "soft_bounce", "deferred", "complaint", "failed"}
    if event_type not in allowed_types:
        db.commit()
        raise ValueError(f"Unsupported webhook event_type '{event_type}'.")

    draft = None
    if provider_message_id:
        draft = db.query(EmailDraft).filter(EmailDraft.provider_message_id == provider_message_id).first()

    suppressed_added = False
    if event_type in ("hard_bounce", "bounced", "complaint"):
        target_email = recipient or (draft.recipient_email.lower() if draft and draft.recipient_email else "")
        if target_email:
            existing_sup = db.query(SuppressionList).filter(SuppressionList.identifier == target_email).first()
            if not existing_sup:
                db.add(SuppressionList(
                    identifier=target_email,
                    channel="email",
                    reason=f"Provider webhook {event_type}: {details or 'permanent failure'}",
                ))
                suppressed_added = True

    if draft:
        if event_type == "delivered" and draft.approval_status in ("sent", "accepted"):
            draft.approval_status = "delivered"
        elif event_type in ("hard_bounce", "bounced"):
            draft.approval_status = "bounced"
            draft.error_message = details or "Hard bounce reported by provider"
        elif event_type == "complaint":
            draft.approval_status = "rejected"
            draft.rejection_reason = details or "Spam complaint reported by provider"
        elif event_type in ("soft_bounce", "deferred"):
            # Transient failure: keep separate from permanent bounces and do NOT suppress
            draft.error_message = details or "Transient delivery deferral"

        db.add(EmailEvent(
            draft_id=draft.id,
            event_type=event_type,
            details=details or f"Webhook event {event_id}: {event_type}",
        ))
        attempt = db.query(EmailSendAttempt).filter(
            EmailSendAttempt.draft_id == draft.id,
            EmailSendAttempt.provider_message_id == provider_message_id,
        ).order_by(EmailSendAttempt.id.desc()).first()
        if attempt:
            attempt.outcome = event_type

    db.commit()
    return {
        "status": "processed",
        "event_id": event_id,
        "event_type": event_type,
        "draft_id": draft.id if draft else None,
        "suppressed_added": suppressed_added,
        "idempotent": False,
    }


def _decode_svix_secret(secret: str) -> bytes:
    import base64
    clean = (secret or "").strip()
    if clean.startswith("whsec_"):
        b64_part = clean[len("whsec_"):]
        return base64.b64decode(b64_part)
    return clean.encode("utf-8")


def verify_resend_svix_signature(
    raw_body: bytes,
    svix_id: Optional[str],
    svix_timestamp: Optional[str],
    svix_signature: Optional[str],
    secret_override: Optional[str] = None,
) -> None:
    """
    Verifies Resend/Svix webhook signatures (svix-id, svix-timestamp, svix-signature)
    against the exact raw request body bytes using RESEND_WEBHOOK_SECRET.
    Rejects missing, expired (>300s), or invalid signatures. Never falls back to generic HMAC.
    """
    import base64
    import hashlib
    import hmac

    secret = (secret_override if secret_override is not None else getattr(settings, "RESEND_WEBHOOK_SECRET", "")) or ""
    if not secret.strip():
        raise PermissionError("Resend webhook rejected: RESEND_WEBHOOK_SECRET is not configured.")
    if not svix_id or not svix_timestamp or not svix_signature:
        raise PermissionError("Resend webhook rejected: missing svix-id, svix-timestamp, or svix-signature header.")

    try:
        ts = int(str(svix_timestamp).strip())
    except ValueError as exc:
        raise PermissionError("Resend webhook rejected: malformed svix-timestamp.") from exc

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if abs(now_ts - ts) > 300:
        raise PermissionError("Resend webhook rejected: svix-timestamp outside 300s replay tolerance.")

    secret_bytes = _decode_svix_secret(secret)
    signed_content = f"{svix_id.strip()}.{svix_timestamp.strip()}.".encode("utf-8") + raw_body
    expected_b64 = base64.b64encode(
        hmac.new(secret_bytes, signed_content, hashlib.sha256).digest()
    ).decode("ascii")

    matched = False
    for token in svix_signature.strip().split():
        if "," in token:
            ver, sig_val = token.split(",", 1)
            if ver == "v1" and hmac.compare_digest(expected_b64, sig_val):
                matched = True
                break

    if not matched:
        raise PermissionError("Resend webhook rejected: invalid Svix v1 signature.")


RESEND_EVENT_MAP = {
    "email.sent": "sent",
    "email.delivered": "delivered",
    "email.delivery_delayed": "deferred",
    "email.bounced": "bounced",
    "email.complained": "complaint",
    "email.failed": "failed",
    "email.suppressed": "rejected",
}


def process_resend_webhook_event(
    db: Session,
    raw_body: bytes,
    svix_id: Optional[str],
    svix_timestamp: Optional[str],
    svix_signature: Optional[str],
    payload: dict,
) -> dict:
    """
    Processes verified Resend Svix webhook events idempotently, mapping Resend event types
    to internal EmailDraft, EmailEvent, EmailSendAttempt, and SuppressionList records.
    """
    from app.models.whatsapp import WebhookEvent

    verify_resend_svix_signature(raw_body, svix_id, svix_timestamp, svix_signature)

    resend_type = str(payload.get("type") or "").strip().lower()
    if resend_type not in RESEND_EVENT_MAP:
        raise ValueError(f"Unsupported Resend webhook event type: '{resend_type}'")

    internal_type = RESEND_EVENT_MAP[resend_type]
    data = payload.get("data") or {}
    email_id = str(data.get("email_id") or "").strip()
    to_list = data.get("to") or []
    recipient = str(to_list[0]).strip().lower() if isinstance(to_list, list) and to_list else ""
    event_id = svix_id.strip()

    # Duplicate Svix event deduplication
    dup = db.query(WebhookEvent).filter(
        WebhookEvent.source == "resend",
        WebhookEvent.event_id == event_id,
    ).first()
    if dup:
        return {"status": "duplicate_ignored", "event_id": event_id, "idempotent": True}

    db.add(WebhookEvent(
        source="resend",
        event_id=event_id,
        idempotency_key=f"resend-svix-{event_id}",
        payload_json=raw_body.decode("utf-8", errors="replace")[:2000],
        status="processed",
    ))

    draft = None
    if email_id:
        draft = db.query(EmailDraft).filter(EmailDraft.provider_message_id == email_id).first()

    suppressed_added = False
    if internal_type in ("bounced", "complaint", "rejected"):
        target_email = recipient or (draft.recipient_email.lower() if draft and draft.recipient_email else "")
        if target_email:
            existing_sup = db.query(SuppressionList).filter(SuppressionList.identifier == target_email).first()
            if not existing_sup:
                db.add(SuppressionList(
                    identifier=target_email,
                    channel="email",
                    reason=f"Resend webhook {resend_type}",
                ))
                suppressed_added = True

    if draft:
        if internal_type == "delivered" and draft.approval_status in ("sent", "accepted"):
            draft.approval_status = "delivered"
        elif internal_type == "sent" and draft.approval_status in ("approved", "sending", "accepted"):
            draft.approval_status = "sent"
        elif internal_type == "bounced":
            draft.approval_status = "bounced"
            draft.error_message = f"Resend reported {resend_type}"
        elif internal_type in ("complaint", "rejected"):
            draft.approval_status = "rejected"
            draft.rejection_reason = f"Resend reported {resend_type}"
        elif internal_type == "failed":
            draft.approval_status = "failed"
            draft.error_message = f"Resend reported {resend_type}"
        elif internal_type == "deferred":
            draft.error_message = "Resend delivery delayed (transient)"

        db.add(EmailEvent(
            draft_id=draft.id,
            event_type=internal_type,
            details=f"Resend Svix {event_id}: {resend_type} (email_id={email_id})",
        ))
        attempt = db.query(EmailSendAttempt).filter(
            EmailSendAttempt.draft_id == draft.id,
            EmailSendAttempt.provider_message_id == email_id,
        ).order_by(EmailSendAttempt.id.desc()).first()
        if attempt:
            attempt.outcome = internal_type

    db.commit()
    return {
        "status": "processed",
        "provider": "resend",
        "event_id": event_id,
        "resend_event": resend_type,
        "internal_event": internal_type,
        "email_id": email_id,
        "draft_id": draft.id if draft else None,
        "suppressed_added": suppressed_added,
        "idempotent": False,
    }


def simulate_local_resend_event(
    db: Session,
    event_type: str,
    event_id: str,
    recipient_email: Optional[str] = None,
    draft_id: Optional[int] = None,
    provider_message_id: Optional[str] = None,
    user_id: Optional[int] = None,
) -> dict:
    """
    Development-only Local Event Simulator.
    Strictly blocked when ENVIRONMENT is production/staging or LIVE_SEND_ENABLED is True.
    Labels all records [SIMULATED] so they can never be confused with genuine Resend webhooks.
    """
    from app.models.whatsapp import WebhookEvent

    env = (getattr(settings, "ENVIRONMENT", "development") or "development").lower()
    if env not in ("development", "test") or getattr(settings, "LIVE_SEND_ENABLED", False):
        raise PermissionError("Local event simulator is strictly restricted to development/test mode with LIVE_SEND_ENABLED=false.")

    allowed_sim = {"email.sent", "email.delivered", "email.delivery_delayed", "email.bounced", "email.complained", "email.failed"}
    clean_type = (event_type or "").strip().lower()
    if clean_type not in allowed_sim:
        raise ValueError(f"Unsupported simulated event '{clean_type}'. Allowed: {sorted(allowed_sim)}")

    clean_event_id = f"sim-{event_id.strip()}"
    dup = db.query(WebhookEvent).filter(
        WebhookEvent.source == "resend_simulated",
        WebhookEvent.event_id == clean_event_id,
    ).first()
    if dup:
        return {"status": "duplicate_ignored", "event_id": clean_event_id, "simulated": True, "idempotent": True}

    internal_type = RESEND_EVENT_MAP[clean_type]
    sim_msg_id = (provider_message_id or f"SIM-{clean_event_id}").strip()

    db.add(WebhookEvent(
        source="resend_simulated",
        event_id=clean_event_id,
        idempotency_key=f"resend-sim-{clean_event_id}",
        payload_json=f'{{"simulated":true,"type":"{clean_type}","recipient":"{recipient_email or ""}"}}',
        status="processed_simulated",
    ))

    draft = None
    if draft_id:
        draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    elif provider_message_id:
        draft = db.query(EmailDraft).filter(EmailDraft.provider_message_id == provider_message_id).first()

    suppressed_added = False
    target_email = (recipient_email or (draft.recipient_email if draft else "") or "").strip().lower()
    if internal_type in ("bounced", "complaint") and target_email:
        existing_sup = db.query(SuppressionList).filter(SuppressionList.identifier == target_email).first()
        if not existing_sup:
            db.add(SuppressionList(
                identifier=target_email,
                channel="email",
                reason=f"[SIMULATED] Resend {clean_type}",
            ))
            suppressed_added = True

    if draft:
        if internal_type == "delivered" and draft.approval_status in ("sent", "accepted", "simulated"):
            draft.approval_status = "delivered"
        elif internal_type == "sent" and draft.approval_status in ("approved", "sending", "accepted"):
            draft.approval_status = "sent"
        elif internal_type == "bounced":
            draft.approval_status = "bounced"
            draft.error_message = f"[SIMULATED] {clean_type}"
        elif internal_type == "complaint":
            draft.approval_status = "rejected"
            draft.rejection_reason = f"[SIMULATED] {clean_type}"
        elif internal_type == "failed":
            draft.approval_status = "failed"
            draft.error_message = f"[SIMULATED] {clean_type}"
        elif internal_type == "deferred":
            draft.error_message = f"[SIMULATED] {clean_type} (transient)"

        db.add(EmailEvent(
            draft_id=draft.id,
            event_type=f"simulated_{internal_type}",
            details=f"[SIMULATED] Local simulator event {clean_event_id}: {clean_type} (ref={sim_msg_id})",
        ))

    record_audit_log(
        db=db,
        action="simulate_resend_event",
        entity_type="email_simulator",
        entity_id=clean_event_id,
        user_id=user_id,
        details={"simulated": True, "resend_event": clean_type, "internal_event": internal_type, "suppressed_added": suppressed_added},
    )
    db.commit()

    return {
        "status": "processed_simulated",
        "simulated": True,
        "label": "SIMULATED",
        "event_id": clean_event_id,
        "resend_event": clean_type,
        "internal_event": internal_type,
        "draft_id": draft.id if draft else None,
        "suppressed_added": suppressed_added,
        "idempotent": False,
    }
