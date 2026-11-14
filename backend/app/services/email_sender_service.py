from datetime import datetime, timezone, date
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from sqlalchemy.orm import Session

from app.models.email import EmailDraft, EmailEvent
from app.models.activity import SuppressionList
from app.models.lead import Lead
from app.schemas.email import EmailSendResult
from app.core.config import settings
from app.core.audit import record_audit_log


def check_daily_sending_limit(db: Session) -> bool:
    """Verifies that daily outbound email count remains strictly under the conservative limit."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.query(EmailEvent).filter(
        EmailEvent.event_type == "sent",
        EmailEvent.timestamp >= today_start
    ).count()
    return count < settings.DEFAULT_DAILY_EMAIL_LIMIT


def send_approved_email(db: Session, draft_id: int, user_id: int) -> EmailSendResult:
    """Sends an email strictly if approved, not suppressed, and within limits."""
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return EmailSendResult(draft_id=draft_id, status="failed", provider="none", message="Draft not found")

    # 1. MANDATORY HUMAN APPROVAL ENFORCEMENT
    if draft.approval_status != "approved":
        return EmailSendResult(
            draft_id=draft_id,
            status="failed",
            provider=draft.provider,
            message="Cannot send: Draft must be explicitly approved by a user before outbound delivery"
        )

    # 2. SUPPRESSION LIST ENFORCEMENT
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

    # 3. CONSERVATIVE DAILY LIMIT CHECK
    if not check_daily_sending_limit(db):
        return EmailSendResult(
            draft_id=draft_id,
            status="queued",
            provider=draft.provider,
            message=f"Daily email limit ({settings.DEFAULT_DAILY_EMAIL_LIMIT}) reached. Message held in queue."
        )

    # 4. DISPATCH VIA CONFIGURED PROVIDER (SMTP / GMAIL / MOCK)
    provider_msg_id = f"acttrident-msg-{draft.id}-{int(datetime.now().timestamp())}"
    send_success = True
    error_msg = None

    if settings.EMAIL_PROVIDER == "smtp" and settings.SMTP_USER and settings.SMTP_PASSWORD:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = draft.subject
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = draft.recipient_email
            
            part1 = MIMEText(draft.body_text, "plain")
            part2 = MIMEText(draft.body_html, "html")
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
        # Test / Mock provider mode: simulates successful delivery without network dependencies
        send_success = True

    if send_success:
        draft.approval_status = "sent"
        draft.sent_at = datetime.now(timezone.utc)
        draft.provider_message_id = provider_msg_id
        
        # Log delivery events
        event_sent = EmailEvent(
            draft_id=draft.id,
            event_type="sent",
            details="Message dispatched through configured mail transport"
        )
        db.add(event_sent)

        event_delivered = EmailEvent(
            draft_id=draft.id,
            event_type="delivered",
            details="Accepted by recipient mail transfer agent"
        )
        db.add(event_delivered)

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
            details=f"SMTP dispatch failure: {error_msg}"
        )
        db.add(event_failed)
        db.commit()

        return EmailSendResult(
            draft_id=draft.id,
            status="failed",
            provider=settings.EMAIL_PROVIDER,
            message=f"Dispatch failed: {error_msg}"
        )
