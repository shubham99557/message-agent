import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
import httpx

from app.models.email import EmailDraft, EmailEvent
from app.models.activity import SuppressionList
from app.models.campaign import Campaign
from app.schemas.email import EmailSendResult
from app.core.config import settings
from app.core.audit import record_audit_log
from app.core.security import compute_content_hash


def check_daily_sending_limit(db: Session, campaign_id: Optional[int] = None) -> bool:
    """Enforces conservative daily email limits across campaigns and global ceiling."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Global daily sent count (excluding simulated)
    global_sent_today = db.query(EmailDraft).filter(
        EmailDraft.sent_at >= today_start,
        EmailDraft.approval_status == "sent"
    ).count()

    if global_sent_today >= settings.DEFAULT_DAILY_EMAIL_LIMIT:
        return False

    # Campaign-level daily sent count
    if campaign_id:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if campaign:
            camp_sent_today = db.query(EmailDraft).filter(
                EmailDraft.campaign_id == campaign_id,
                EmailDraft.sent_at >= today_start,
                EmailDraft.approval_status == "sent"
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


def _send_via_gmail_api(draft: EmailDraft, body_with_optout: str) -> str:
    """Dispatches RFC 2822 message through official Google Gmail REST API."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = draft.subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = draft.recipient_email

    msg.attach(MIMEText(body_with_optout, "plain"))
    if draft.body_html:
        msg.attach(MIMEText(draft.body_html, "html"))

    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    
    token = settings.GMAIL_ACCESS_TOKEN
    # If refresh token available, request fresh access token
    if not token and settings.GMAIL_REFRESH_TOKEN and settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET:
        with httpx.Client(timeout=8.0) as client:
            token_resp = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.GMAIL_CLIENT_ID,
                    "client_secret": settings.GMAIL_CLIENT_SECRET,
                    "refresh_token": settings.GMAIL_REFRESH_TOKEN,
                    "grant_type": "refresh_token"
                }
            )
            if token_resp.status_code == 200:
                token = token_resp.json().get("access_token")

    if not token:
        raise RuntimeError("No valid Gmail API access token or OAuth credentials configured.")

    with httpx.Client(timeout=10.0) as client:
        resp = client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"raw": raw_message}
        )
        resp.raise_for_status()
        return resp.json().get("id") or f"gmail-{int(datetime.now().timestamp())}"


def send_approved_email(
    db: Session,
    draft_id: int,
    user_id: int
) -> EmailSendResult:
    """Dispatches an email draft strictly after validating Human Approval, Content Hash, and Suppression."""
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return EmailSendResult(
            draft_id=draft_id,
            status="failed",
            provider=settings.EMAIL_PROVIDER,
            message="Email draft not found"
        )

    # 1. MANDATORY HUMAN APPROVAL ENFORCEMENT
    if draft.approval_status != "approved":
        return EmailSendResult(
            draft_id=draft_id,
            status="failed",
            provider=draft.provider,
            message="Security Block: Email has not been approved by a designated reviewer"
        )

    # 2. IMMUTABLE CONTENT HASH VERIFICATION
    current_hash = compute_content_hash([draft.subject, draft.body_text])
    if not draft.approved_content_hash or current_hash != draft.approved_content_hash:
        # Invalidate approval immediately if content mismatch detected
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

    # 3. SUPPRESSION LIST ENFORCEMENT
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

    # 4. CONSERVATIVE DAILY LIMIT CHECK
    if not check_daily_sending_limit(db, draft.campaign_id):
        return EmailSendResult(
            draft_id=draft_id,
            status="queued",
            provider=draft.provider,
            message=f"Daily email limit ({settings.DEFAULT_DAILY_EMAIL_LIMIT}) reached. Message held in queue."
        )

    # 5. DISPATCH VIA CONFIGURED PROVIDER (GMAIL / SMTP / MOCK)
    provider_msg_id = f"acttrident-msg-{draft.id}-{int(datetime.now().timestamp())}"
    send_success = True
    error_msg = None
    is_mock = False
    body_with_optout = _ensure_opt_out_footer(draft)

    if settings.EMAIL_PROVIDER == "gmail" and (settings.GMAIL_ACCESS_TOKEN or settings.GMAIL_REFRESH_TOKEN):
        try:
            provider_msg_id = _send_via_gmail_api(draft, body_with_optout)
        except Exception as e:
            send_success = False
            error_msg = f"Gmail API error: {e}"
    elif settings.EMAIL_PROVIDER == "smtp" and settings.SMTP_USER and settings.SMTP_PASSWORD:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = draft.subject
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = draft.recipient_email
            
            part1 = MIMEText(body_with_optout, "plain")
            part2 = MIMEText(draft.body_html or body_with_optout, "html")
            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, draft.recipient_email, msg.as_string())
        except Exception as e:
            send_success = False
            error_msg = str(e)
    else:
        # Explicit mock mode: must NEVER report simulated messages as real 'sent' or 'delivered'
        is_mock = True

    if is_mock:
        # Accurately record mock dispatch without falsifying delivery metrics
        draft.approval_status = "simulated"
        draft.provider_message_id = f"sim-{provider_msg_id}"
        event_sim = EmailEvent(
            draft_id=draft.id,
            event_type="simulated",
            details="Simulated dispatch in test environment without network transmission"
        )
        db.add(event_sim)
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
            message="Message dispatch simulated (mock provider active; no live external email sent)"
        )

    if send_success:
        draft.approval_status = "sent"
        draft.sent_at = datetime.now(timezone.utc)
        draft.provider_message_id = provider_msg_id
        
        event_sent = EmailEvent(
            draft_id=draft.id,
            event_type="sent",
            details="Message dispatched through configured mail transport"
        )
        db.add(event_sent)

        # Update CRM Lead
        if draft.company and draft.company.lead:
            draft.company.lead.pipeline_status = "contacted"
            draft.company.lead.last_contact_date = datetime.now(timezone.utc)

        db.commit()

        record_audit_log(
            db=db,
            action="send_email",
            entity_type="email_draft",
            entity_id=str(draft.id),
            user_id=user_id,
            details={"recipient": draft.recipient_email, "subject": draft.subject}
        )

        return EmailSendResult(
            draft_id=draft.id,
            status="sent",
            provider=settings.EMAIL_PROVIDER,
            message="Email successfully dispatched"
        )
    else:
        draft.error_message = error_msg
        event_failed = EmailEvent(
            draft_id=draft.id,
            event_type="bounced",
            details=f"Dispatch failure: {error_msg}"
        )
        db.add(event_failed)
        db.commit()
        return EmailSendResult(
            draft_id=draft.id,
            status="failed",
            provider=settings.EMAIL_PROVIDER,
            message=f"Dispatch failed: {error_msg}"
        )


def send_email(db: Session, draft: EmailDraft) -> EmailSendResult:
    """Convenience alias for background job worker dispatch."""
    return send_approved_email(db, draft.id, user_id=1)
