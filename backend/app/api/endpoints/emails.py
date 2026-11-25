from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.core.config import settings
from app.models.user import User
from app.models.email import EmailDraft, EmailSendAttempt
from app.schemas.email import (
    EmailGenerateRequest,
    EmailVariationsRequest,
    EmailVariationsResponse,
    EmailDraftResponse,
    EmailDraftUpdate,
    EmailSendResult
)
from app.services.email_generator_service import generate_email_draft, generate_email_variations
from app.services.approval_service import enrich_draft_response, edit_email_draft
from app.services.email_sender_service import (
    send_approved_email,
    record_provider_email_event,
    send_test_mode_email,
    process_provider_webhook_event,
    process_resend_webhook_event,
    simulate_local_resend_event,
    RESEND_TEST_RECIPIENTS,
)
from app.services.dns_auth_service import run_domain_auth_preflight
from app.services.company_service import get_company
from app.core.audit import record_audit_log

router = APIRouter()


class ProviderEmailEventPayload(BaseModel):
    provider_message_id: str
    event_type: str  # delivered, bounced, complaint, opened, clicked
    details: Optional[str] = None


@router.get("/drafts", response_model=List[EmailDraftResponse])
def list_email_drafts(
    company_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List email drafts, optionally filtered by company_id."""
    query = db.query(EmailDraft)
    if company_id is not None:
        query = query.filter(EmailDraft.company_id == company_id)
    drafts = query.order_by(EmailDraft.created_at.desc()).limit(limit).all()
    return [enrich_draft_response(db, d) for d in drafts]


@router.post("/generate-variations", response_model=EmailVariationsResponse)
def generate_email_variations_endpoint(
    req: EmailVariationsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    """
    Phase 3: Generate 3 personalized email variations (short intro, standard, consultative)
    grounded strictly in company research dossier, verified contacts, and service catalog.
    Synthetic test fixtures are strictly blocked from generating outreach.
    """
    company = get_company(db, req.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    try:
        variations_res = generate_email_variations(
            db=db,
            company=company,
            contact_id=req.contact_id,
            tone=req.tone,
            service_id=req.service_id,
            custom_notes=req.custom_notes
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    record_audit_log(
        db=db,
        action="generate_email_variations",
        entity_type="company",
        entity_id=str(company.id),
        user_id=current_user.id,
        details={"company": company.name, "tone": req.tone, "variations_count": len(variations_res.variations)}
    )
    return variations_res


@router.post("/generate", response_model=EmailDraftResponse, status_code=status.HTTP_201_CREATED)
def generate_email_endpoint(
    req: EmailGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    company = get_company(db, req.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    try:
        draft = generate_email_draft(
            db=db,
            company=company,
            contact_id=req.contact_id,
            campaign_id=req.campaign_id,
            tone=req.tone,
            draft_type=req.draft_type or "initial_email",
            service_id=req.service_id,
            custom_notes=req.custom_notes,
            variation_type=req.variation_type or "standard"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    
    record_audit_log(
        db=db,
        action="generate_email_draft",
        entity_type="email_draft",
        entity_id=str(draft.id),
        user_id=current_user.id,
        details={"company": company.name, "tone": req.tone, "variation_type": req.variation_type or "standard"}
    )
    return enrich_draft_response(db, draft)


@router.get("/drafts/{draft_id}", response_model=EmailDraftResponse)
def get_email_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return enrich_draft_response(db, draft)


def _check_draft_ownership(draft: EmailDraft, current_user: User) -> None:
    """Ensures sales_rep users can only edit/inspect drafts belonging to their own companies or campaigns."""
    if current_user.role in ["admin", "manager"]:
        return
    owns_company = bool(draft.company and draft.company.created_by_id == current_user.id)
    owns_campaign = bool(draft.campaign and draft.campaign.created_by_id == current_user.id)
    if not (owns_company or owns_campaign):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: You do not own this email draft or require manager privileges.",
        )


@router.put("/drafts/{draft_id}", response_model=EmailDraftResponse)
def update_email_draft_endpoint(
    draft_id: int,
    update_in: EmailDraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"]))
):
    existing = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Draft not found")
    _check_draft_ownership(existing, current_user)
    if existing.approval_status in ("sending", "sent", "delivered"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit email draft in final status '{existing.approval_status}'.",
        )

    try:
        draft = edit_email_draft(
            db=db,
            draft_id=draft_id,
            update_in=update_in,
            user_id=current_user.id,
            user_role=current_user.role
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    record_audit_log(
        db=db,
        action="update_email_draft",
        entity_type="email_draft",
        entity_id=str(draft.id),
        user_id=current_user.id,
        details={"new_version": draft.version, "approval_status": draft.approval_status}
    )
    return enrich_draft_response(db, draft)


@router.post("/send/{draft_id}", response_model=EmailSendResult)
def send_email_endpoint(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    result = send_approved_email(db, draft_id, current_user.id)
    if result.status == "rate_limited":
        raise HTTPException(status_code=429, detail=result.message)
    if result.status == "blocked_kill_switch":
        raise HTTPException(status_code=423, detail=result.message)
    if result.status == "blocked_campaign_inactive":
        raise HTTPException(status_code=409, detail=result.message)
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.message)
    return result


@router.get("/drafts/{draft_id}/attempts")
def get_draft_send_attempts(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns separate send-attempt audit records for a draft (owner or admin/manager)."""
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    _check_draft_ownership(draft, current_user)
    attempts = (
        db.query(EmailSendAttempt)
        .filter(EmailSendAttempt.draft_id == draft_id)
        .order_by(EmailSendAttempt.attempt_number.asc())
        .all()
    )
    return [
        {
            "id": a.id,
            "draft_id": a.draft_id,
            "attempt_number": a.attempt_number,
            "idempotency_key": a.idempotency_key,
            "provider": a.provider,
            "outcome": a.outcome,
            "provider_message_id": a.provider_message_id,
            "provider_thread_id": a.provider_thread_id,
            "error_code": a.error_code,
            "error_message": a.error_message,
            "created_at": a.created_at,
        }
        for a in attempts
    ]


@router.post("/events/provider")
def ingest_provider_email_event(
    payload: ProviderEmailEventPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Records a provider-confirmed delivery, bounce, or complaint event."""
    try:
        draft = record_provider_email_event(
            db=db,
            provider_message_id=payload.provider_message_id,
            event_type=payload.event_type,
            details=payload.details,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not draft:
        raise HTTPException(status_code=404, detail="No email draft matches that provider_message_id.")

    return {
        "draft_id": draft.id,
        "approval_status": draft.approval_status,
        "provider_message_id": draft.provider_message_id,
        "event_type": payload.event_type,
    }


class TestModeSendPayload(BaseModel):
    recipient_email: str
    subject: str
    body_text: str
    idempotency_key: str
    provider_override: Optional[str] = None


@router.get("/dns-check")
def check_domain_dns_auth(
    domain: str = Query(..., min_length=3),
    selector: Optional[str] = Query(None),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Read-only DNS preflight check for SPF, DKIM, and DMARC."""
    dkim_sel = selector or getattr(settings, "EMAIL_DKIM_SELECTOR", "default") or "default"
    try:
        return run_domain_auth_preflight(domain=domain, dkim_selector=dkim_sel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/test-mode/status")
def get_email_test_mode_status(
    current_user: User = Depends(require_role(["admin", "manager", "sales_rep"])),
):
    """Returns safe non-secret configuration status for Phase 4A.1 Resend test-mode email delivery."""
    raw_allow = getattr(settings, "EMAIL_TEST_ALLOWLIST", "") or ""
    allowlist = [a.strip().lower() for a in raw_allow.split(",") if a.strip()]
    return {
        "live_send_enabled": settings.LIVE_SEND_ENABLED,
        "test_mode_enabled": getattr(settings, "EMAIL_TEST_MODE_ENABLED", False),
        "primary_provider": getattr(settings, "EMAIL_PROVIDER", "resend"),
        "sandbox_provider": getattr(settings, "EMAIL_SANDBOX_PROVIDER", "resend"),
        "resend_from_email": getattr(settings, "RESEND_FROM_EMAIL", "onboarding@resend.dev"),
        "resend_test_recipients": sorted(RESEND_TEST_RECIPIENTS),
        "allowlist_count": len(allowlist),
        "allowlist": allowlist,
        "dkim_selector": getattr(settings, "EMAIL_DKIM_SELECTOR", "resend"),
        "public_base_url": getattr(settings, "PUBLIC_BASE_URL", "http://localhost:8000"),
        "resend_api_key_configured": bool((getattr(settings, "RESEND_API_KEY", "") or "").strip()),
        "resend_webhook_secret_configured": bool((getattr(settings, "RESEND_WEBHOOK_SECRET", "") or "").strip()),
        "api_key_configured": bool((getattr(settings, "RESEND_API_KEY", "") or getattr(settings, "EMAIL_PROVIDER_API_KEY", "") or "").strip()),
        "webhook_secret_configured": bool((getattr(settings, "RESEND_WEBHOOK_SECRET", "") or getattr(settings, "EMAIL_WEBHOOK_SECRET", "") or "").strip()),
    }


@router.post("/test-mode/send")
def send_test_mode_email_endpoint(
    payload: TestModeSendPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Dispatches a test-mode email strictly to operator-allowlisted addresses."""
    try:
        return send_test_mode_email(
            db=db,
            recipient_email=payload.recipient_email,
            subject=payload.subject,
            body_text=payload.body_text,
            user_id=current_user.id,
            idempotency_key=payload.idempotency_key,
            provider_override=payload.provider_override,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class SimulateEventPayload(BaseModel):
    event_type: str
    event_id: str
    recipient_email: Optional[str] = None
    draft_id: Optional[int] = None
    provider_message_id: Optional[str] = None


@router.post("/test-mode/simulate-event")
def simulate_resend_event_endpoint(
    payload: SimulateEventPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """
    Development-only local Resend event simulator.
    Marks all events [SIMULATED] and never weakens Svix verification on live webhook routes.
    """
    try:
        return simulate_local_resend_event(
            db=db,
            event_type=payload.event_type,
            event_id=payload.event_id,
            recipient_email=payload.recipient_email,
            draft_id=payload.draft_id,
            provider_message_id=payload.provider_message_id,
            user_id=current_user.id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/webhooks/resend")
async def resend_webhook_endpoint(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticated Resend Svix webhook endpoint (svix-id, svix-timestamp, svix-signature).
    Verifies against raw request body bytes using RESEND_WEBHOOK_SECRET.
    """
    raw_body = await request.body()
    svix_id = request.headers.get("svix-id")
    svix_ts = request.headers.get("svix-timestamp")
    svix_sig = request.headers.get("svix-signature")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON webhook payload.")

    try:
        return process_resend_webhook_event(
            db=db,
            raw_body=raw_body,
            svix_id=svix_id,
            svix_timestamp=svix_ts,
            svix_signature=svix_sig,
            payload=payload,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/webhooks/provider")
async def provider_email_webhook_endpoint(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticated provider webhook endpoint.
    Uses Resend Svix verification when Svix headers are present or EMAIL_PROVIDER=resend;
    never substitutes generic HMAC for Resend Svix verification.
    """
    raw_body = await request.body()
    svix_id = request.headers.get("svix-id")
    svix_ts = request.headers.get("svix-timestamp")
    svix_sig = request.headers.get("svix-signature")
    sig = request.headers.get("X-ActTrident-Signature") or request.headers.get("X-Postmark-Signature")
    ts = request.headers.get("X-ActTrident-Timestamp")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON webhook payload.")

    try:
        if svix_id or svix_sig or (getattr(settings, "EMAIL_PROVIDER", "resend") == "resend" and "type" in payload):
            return process_resend_webhook_event(
                db=db,
                raw_body=raw_body,
                svix_id=svix_id,
                svix_timestamp=svix_ts,
                svix_signature=svix_sig,
                payload=payload,
            )
        return process_provider_webhook_event(
            db=db,
            raw_body=raw_body,
            signature_header=sig,
            timestamp_header=ts,
            payload=payload,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/drafts/{draft_id}/timeline")
def get_draft_timeline(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns chronological lifecycle, provider, and clearly labeled [SIMULATED] events for a draft."""
    from app.models.email import ApprovalRecord, EmailEvent
    from app.models.activity import AuditLog, SuppressionList

    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    _check_draft_ownership(draft, current_user)

    timeline = []
    if draft.created_at:
        timeline.append({
            "id": f"draft-created-{draft.id}",
            "timestamp": draft.created_at.isoformat(),
            "event_type": "draft_created",
            "label": "Draft created",
            "source": "system_draft",
            "is_simulated": False,
            "details": f"Version {draft.version or 1} created for {draft.recipient_email or 'unassigned recipient'}",
        })

    audit_rows = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "email_draft", AuditLog.entity_id == str(draft.id))
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
    seen_approval_actions = set()
    for a in audit_rows:
        ts = a.timestamp.isoformat() if a.timestamp else None
        act = (a.action or "").lower()
        if act == "update_email_draft":
            label = "Draft edited"
        elif act in ("request_approval", "submit_for_approval"):
            label = "Approval requested"
        elif act == "approve_email_draft":
            label = "Draft approved"
            seen_approval_actions.add("approved")
        elif act == "reject_email_draft":
            label = "Draft rejected"
            seen_approval_actions.add("rejected")
        elif act == "skip_email_draft":
            label = "Draft skipped"
        else:
            label = act.replace("_", " ").capitalize()
        timeline.append({
            "id": f"audit-{a.id}",
            "timestamp": ts,
            "event_type": act,
            "label": label,
            "source": "operator_audit",
            "is_simulated": False,
            "details": a.details,
        })

    approvals = (
        db.query(ApprovalRecord)
        .filter(ApprovalRecord.entity_type == "email_draft", ApprovalRecord.entity_id == draft.id)
        .order_by(ApprovalRecord.created_at.asc())
        .all()
    )
    for rec in approvals:
        dec = (rec.action or "").lower()
        if dec in seen_approval_actions:
            continue
        timeline.append({
            "id": f"approval-{rec.id}",
            "timestamp": rec.created_at.isoformat() if rec.created_at else None,
            "event_type": f"draft_{dec}",
            "label": f"Draft {dec}",
            "source": "human_approval",
            "is_simulated": False,
            "details": rec.reason or f"Approver ID {rec.approver_id}",
        })

    attempts = (
        db.query(EmailSendAttempt)
        .filter(EmailSendAttempt.draft_id == draft.id)
        .order_by(EmailSendAttempt.created_at.asc())
        .all()
    )
    for att in attempts:
        outcome = (att.outcome or "").lower()
        prov = att.provider or "resend"
        if outcome in ("sent", "accepted", "test_mode_sent"):
            label = f"Test email accepted by {prov.capitalize()} (not yet delivered)"
        elif outcome in ("blocked", "blocked_kill_switch", "blocked_test_mode"):
            label = f"Send blocked ({outcome})"
        else:
            label = f"Send attempt: {outcome}"
        timeline.append({
            "id": f"attempt-{att.id}",
            "timestamp": att.created_at.isoformat() if att.created_at else None,
            "event_type": f"send_{outcome}",
            "label": label,
            "source": f"provider_{prov}",
            "is_simulated": False,
            "details": att.provider_message_id or att.error_message or att.idempotency_key,
        })

    events = (
        db.query(EmailEvent)
        .filter(EmailEvent.draft_id == draft.id)
        .order_by(EmailEvent.timestamp.asc())
        .all()
    )
    event_labels = {
        "sent": "Accepted by provider (not yet delivered)",
        "accepted": "Accepted by provider (not yet delivered)",
        "delivered": "Delivered",
        "bounce": "Bounced",
        "bounced": "Bounced",
        "complaint": "Complaint received",
        "complained": "Complaint received",
        "unsubscribe": "Unsubscribed",
        "unsubscribed": "Unsubscribed",
        "deferred": "Delivery delayed",
        "failed": "Delivery failed",
    }
    for ev in events:
        etype = (ev.event_type or "").lower()
        is_sim = etype.startswith("simulated_") or "[simulated]" in (ev.details or "").lower()
        base_type = etype.replace("simulated_", "", 1)
        human_label = event_labels.get(base_type, base_type.replace("_", " ").capitalize())
        if is_sim:
            human_label = f"[SIMULATED] {human_label}"
            src = "local_simulator"
        elif base_type in ("unsubscribe", "unsubscribed"):
            src = "unsubscribe_endpoint"
        else:
            src = "provider_webhook"
        timeline.append({
            "id": f"event-{ev.id}",
            "timestamp": ev.timestamp.isoformat() if ev.timestamp else None,
            "event_type": etype,
            "label": human_label,
            "source": src,
            "is_simulated": is_sim,
            "details": ev.details,
        })

    if draft.recipient_email:
        supp = (
            db.query(SuppressionList)
            .filter(SuppressionList.identifier == draft.recipient_email.strip().lower())
            .first()
        )
        if supp and ("unsubscrib" in (supp.reason or "").lower()):
            timeline.append({
                "id": f"supp-{supp.id}",
                "timestamp": supp.created_at.isoformat() if supp.created_at else None,
                "event_type": "unsubscribed",
                "label": "Unsubscribed (Suppression Registry)",
                "source": "unsubscribe_endpoint",
                "is_simulated": False,
                "details": supp.reason,
            })

    timeline.sort(key=lambda item: item.get("timestamp") or "")
    return {
        "draft_id": draft.id,
        "approval_status": draft.approval_status,
        "recipient_email": draft.recipient_email,
        "items": timeline,
    }
