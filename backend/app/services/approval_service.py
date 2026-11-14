from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.email import EmailDraft, EmailEvent
from app.models.company import Company
from app.models.consent import ContactConsent
from app.schemas.email import EmailDraftResponse, EmailDraftUpdate, BulkApprovalRequest
from app.core.audit import record_audit_log


def enrich_draft_response(db: Session, draft: EmailDraft) -> EmailDraftResponse:
    """Enriches draft with compliance and source attribution data for the Human Approval UI."""
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


def approve_email_draft(db: Session, draft_id: int, user_id: int) -> Optional[EmailDraft]:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return None

    draft.approval_status = "approved"
    draft.approved_by_id = user_id
    draft.approved_at = datetime.now(timezone.utc)
    
    # Update lead status to awaiting_approval or ready for sending
    if draft.company and draft.company.lead:
        draft.company.lead.pipeline_status = "awaiting_approval"

    db.commit()
    db.refresh(draft)
    return draft


def reject_email_draft(db: Session, draft_id: int, user_id: int, reason: Optional[str] = None) -> Optional[EmailDraft]:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return None

    draft.approval_status = "rejected"
    draft.rejection_reason = reason or "Rejected during human review"
    db.commit()
    db.refresh(draft)
    return draft


def skip_email_draft(db: Session, draft_id: int, user_id: int) -> Optional[EmailDraft]:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return None

    draft.approval_status = "skipped"
    db.commit()
    db.refresh(draft)
    return draft


def edit_email_draft(db: Session, draft_id: int, update_in: EmailDraftUpdate, user_id: int) -> Optional[EmailDraft]:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return None

    if update_in.subject is not None:
        draft.subject = update_in.subject
    if update_in.body_text is not None:
        draft.body_text = update_in.body_text
    if update_in.body_html is not None:
        draft.body_html = update_in.body_html
    if update_in.approval_status is not None:
        draft.approval_status = update_in.approval_status
        if update_in.approval_status == "approved":
            draft.approved_by_id = user_id
            draft.approved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(draft)
    return draft


def bulk_handle_approvals(db: Session, bulk_req: BulkApprovalRequest, user_id: int) -> dict:
    processed = 0
    for draft_id in bulk_req.draft_ids:
        if bulk_req.action == "approve":
            approve_email_draft(db, draft_id, user_id)
            processed += 1
        elif bulk_req.action == "reject":
            reject_email_draft(db, draft_id, user_id, bulk_req.reason)
            processed += 1
        elif bulk_req.action == "skip":
            skip_email_draft(db, draft_id, user_id)
            processed += 1

    return {"status": "success", "action": bulk_req.action, "processed_count": processed}
