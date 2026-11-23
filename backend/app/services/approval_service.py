from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.email import EmailDraft, EmailEvent, ApprovalRecord
from app.models.company import Company
from app.models.consent import ContactConsent
from app.schemas.email import EmailDraftResponse, EmailDraftUpdate, BulkApprovalRequest
from app.core.audit import record_audit_log
from app.core.security import compute_content_hash


def enrich_draft_response(db: Session, draft: EmailDraft) -> EmailDraftResponse:
    """Enriches draft with compliance, content hash, and source attribution data for the Human Approval UI."""
    company = draft.company
    contact_source_url = None
    consent_status = "unconsented"

    if company:
        # Get source of email
        source = next((s for s in company.sources if s.field_name == "public_email"), None)
        if not source and company.sources:
            source = company.sources[0]
        contact_source_url = source.source_url if source else (company.website or "Direct Entry")

        # Get consent status
        consent = db.query(ContactConsent).filter(
            ContactConsent.company_id == company.id,
            ContactConsent.channel == "email"
        ).first()
        if consent:
            consent_status = consent.consent_status

    return EmailDraftResponse(
        id=draft.id,
        campaign_id=draft.campaign_id,
        company_id=draft.company_id,
        contact_id=draft.contact_id,
        recipient_email=draft.recipient_email,
        recipient_name=draft.recipient_name,
        subject=draft.subject,
        body_html=draft.body_html,
        body_text=draft.body_text,
        tone=draft.tone,
        approval_status=draft.approval_status,
        approved_by_id=draft.approved_by_id,
        approved_at=draft.approved_at,
        scheduled_at=getattr(draft, "scheduled_at", None),
        rejection_reason=draft.rejection_reason,
        sent_at=draft.sent_at,
        provider=draft.provider,
        provider_message_id=draft.provider_message_id,
        error_message=draft.error_message,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        events=draft.events or [],
        company_name=company.name if company else None,
        company_city=company.city if company else None,
        contact_source_url=contact_source_url,
        consent_status=consent_status,
        campaign_name=draft.campaign.name if draft.campaign else "Direct Outreach"
    )


def list_approval_queue(
    db: Session,
    status_filter: Optional[str] = "draft",
    campaign_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50
) -> Tuple[List[EmailDraftResponse], int]:
    query = db.query(EmailDraft)

    if status_filter and status_filter.lower() != "all":
        query = query.filter(EmailDraft.approval_status == status_filter)

    if campaign_id:
        query = query.filter(EmailDraft.campaign_id == campaign_id)

    total = query.count()
    drafts = query.order_by(EmailDraft.created_at.desc()).offset(skip).limit(limit).all()
    enriched = [enrich_draft_response(db, d) for d in drafts]
    return enriched, total


def _log_approval_record(
    db: Session,
    entity_type: str,
    entity_id: int,
    approver_id: Optional[int],
    action: str,
    content_version: int,
    content_hash: str,
    reason: Optional[str] = None
) -> ApprovalRecord:
    rec = ApprovalRecord(
        entity_type=entity_type,
        entity_id=entity_id,
        approver_id=approver_id,
        action=action,
        content_version=content_version or 1,
        content_hash=content_hash,
        reason=reason,
        created_at=datetime.now(timezone.utc)
    )
    db.add(rec)
    return rec


def approve_email_draft(db: Session, draft_id: int, user_id: int) -> Optional[EmailDraft]:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return None
    if not draft.recipient_email or not draft.recipient_email.strip():
        draft.approval_status = "missing_recipient"
        db.commit()
        return None
    if draft.approval_status in ("sending", "sent", "delivered"):
        return draft

    # Compute and bind immutable content hash to approval record
    current_hash = compute_content_hash([draft.subject, draft.body_text])
    draft.content_hash = current_hash
    draft.approved_content_hash = current_hash
    draft.approval_status = "approved"
    draft.approved_by_id = user_id
    draft.approved_at = datetime.now(timezone.utc)

    _log_approval_record(
        db=db,
        entity_type="email_draft",
        entity_id=draft.id,
        approver_id=user_id,
        action="approved",
        content_version=draft.version or 1,
        content_hash=current_hash
    )
    
    # Update lead status to awaiting_approval / ready
    if draft.company and draft.company.lead:
        draft.company.lead.pipeline_status = "awaiting_approval"

    db.commit()
    db.refresh(draft)
    return draft


def reject_email_draft(db: Session, draft_id: int, user_id: int, reason: Optional[str] = None) -> Optional[EmailDraft]:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return None

    current_hash = compute_content_hash([draft.subject, draft.body_text])
    draft.approval_status = "rejected"
    draft.rejection_reason = reason or "Rejected during human review"
    draft.approved_content_hash = None
    _log_approval_record(
        db=db,
        entity_type="email_draft",
        entity_id=draft.id,
        approver_id=user_id,
        action="rejected",
        content_version=draft.version or 1,
        content_hash=current_hash,
        reason=draft.rejection_reason
    )
    db.commit()
    db.refresh(draft)
    return draft


def skip_email_draft(db: Session, draft_id: int, user_id: int) -> Optional[EmailDraft]:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return None

    current_hash = compute_content_hash([draft.subject, draft.body_text])
    draft.approval_status = "skipped"
    _log_approval_record(
        db=db,
        entity_type="email_draft",
        entity_id=draft.id,
        approver_id=user_id,
        action="skipped",
        content_version=draft.version or 1,
        content_hash=current_hash
    )
    db.commit()
    db.refresh(draft)
    return draft


def edit_email_draft(
    db: Session,
    draft_id: int,
    update_in: EmailDraftUpdate,
    user_id: int,
    user_role: str = "sales_rep"
) -> Optional[EmailDraft]:
    """
    Editing a draft MUST NEVER implicitly approve it.
    Any content change increments version, recalculates content hash, invalidates prior approval,
    and writes an immutable ApprovalRecord entry.
    """
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return None

    was_approved = draft.approval_status == "approved"
    content_changed = False
    if update_in.recipient_email is not None and update_in.recipient_email != draft.recipient_email:
        draft.recipient_email = update_in.recipient_email
        content_changed = True
    if update_in.subject is not None and update_in.subject != draft.subject:
        draft.subject = update_in.subject
        content_changed = True
    if update_in.body_text is not None and update_in.body_text != draft.body_text:
        draft.body_text = update_in.body_text
        content_changed = True
    if update_in.body_html is not None and update_in.body_html != draft.body_html:
        draft.body_html = update_in.body_html
        content_changed = True

    if content_changed:
        draft.version = (draft.version or 1) + 1
        new_hash = compute_content_hash([draft.subject, draft.body_text])
        draft.content_hash = new_hash
        # Invalidate approval immediately on content modification — explicit re-approval required
        draft.approval_status = "draft"
        draft.approved_by_id = None
        draft.approved_at = None
        draft.approved_content_hash = None
        if was_approved:
            _log_approval_record(
                db=db,
                entity_type="email_draft",
                entity_id=draft.id,
                approver_id=user_id,
                action="invalidated_by_edit",
                content_version=draft.version,
                content_hash=new_hash,
                reason="Prior approval invalidated after draft content modification"
            )

    # Strict rule: Editing endpoint can ONLY move to non-approved draft states (draft, awaiting_approval, cancelled)
    # Implicit approval via PUT /emails/drafts/{id} is strictly forbidden.
    if update_in.approval_status is not None and not content_changed:
        if update_in.approval_status in ("draft", "awaiting_approval", "cancelled"):
            draft.approval_status = update_in.approval_status

    db.commit()
    db.refresh(draft)
    return draft


def bulk_handle_approvals(db: Session, bulk_req: BulkApprovalRequest, user_id: int) -> dict:
    if bulk_req.action == "approve":
        raise ValueError("Bulk outbound approval is strictly prohibited. Each message requires individual human operator review.")

    processed = 0
    for draft_id in bulk_req.draft_ids:
        if bulk_req.action == "reject":
            reject_email_draft(db, draft_id, user_id, bulk_req.reason)
            processed += 1
        elif bulk_req.action == "skip":
            skip_email_draft(db, draft_id, user_id)
            processed += 1

    return {"status": "success", "action": bulk_req.action, "processed_count": processed}


def regenerate_email_draft(
    db: Session,
    draft_id: int,
    user_id: int,
    tone: Optional[str] = None,
    custom_notes: Optional[str] = None
) -> Optional[EmailDraft]:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return None
    if draft.approval_status in ("sending", "sent", "delivered"):
        return draft

    from app.services.email_generator_service import build_email_content

    company = draft.company
    if not company:
        return None

    effective_tone = tone or draft.tone or "Friendly professional"
    subject, body_text, body_html = build_email_content(
        company=company,
        contact=draft.contact,
        tone=effective_tone,
        custom_notes=custom_notes
    )

    draft.subject = subject
    draft.body_text = body_text
    draft.body_html = body_html
    draft.tone = effective_tone
    draft.version = (draft.version or 1) + 1
    new_hash = compute_content_hash([subject, body_text])
    draft.content_hash = new_hash
    draft.approval_status = "draft"
    draft.approved_by_id = None
    draft.approved_at = None
    draft.approved_content_hash = None

    _log_approval_record(
        db=db,
        entity_type="email_draft",
        entity_id=draft.id,
        approver_id=user_id,
        action="regenerated",
        content_version=draft.version,
        content_hash=new_hash,
        reason=f"Regenerated with tone: {effective_tone}"
    )
    db.commit()
    db.refresh(draft)
    return draft


def schedule_email_draft(
    db: Session,
    draft_id: int,
    user_id: int,
    scheduled_at: datetime
) -> Optional[EmailDraft]:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return None

    draft.scheduled_at = scheduled_at
    current_hash = (
        draft.content_hash
        or draft.approved_content_hash
        or compute_content_hash([draft.subject, draft.body_text])
    )
    _log_approval_record(
        db=db,
        entity_type="email_draft",
        entity_id=draft.id,
        approver_id=user_id,
        action="scheduled",
        content_version=draft.version or 1,
        content_hash=current_hash,
        reason=f"Scheduled for {scheduled_at.isoformat()}"
    )
    db.commit()
    db.refresh(draft)
    return draft
