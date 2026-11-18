from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User
from app.models.whatsapp import WhatsAppTemplate, WhatsAppMessage
from app.schemas.whatsapp import (
    WhatsAppTemplateResponse,
    WhatsAppDraftRequest,
    WhatsAppMessageResponse,
    ContactConsentCreate,
    ContactConsentResponse
)
from app.services.whatsapp_service import (
    seed_default_meta_templates,
    create_whatsapp_message,
    send_approved_whatsapp_message,
    approve_whatsapp_message_internal,
    record_contact_consent,
    process_incoming_meta_webhook
)
from app.services.company_service import get_company
from app.core.config import settings
from app.core.audit import record_audit_log
from app.integrations.whatsapp_adapter import (
    get_whatsapp_connection_status,
    check_meta_connection_health,
    sync_meta_templates,
    MetaWhatsAppError,
)

router = APIRouter()


@router.get("/status")
def whatsapp_connection_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns honest Meta WhatsApp Cloud API connection and simulation status."""
    return get_whatsapp_connection_status(db)


@router.post("/health-check")
def whatsapp_health_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Queries Meta Graph API to validate credentials and phone number health."""
    try:
        res = check_meta_connection_health(db)
        record_audit_log(
            db=db,
            action="whatsapp_health_check",
            entity_type="channel_connection",
            user_id=current_user.id,
            details={"status": res["status"], "verified_name": res.get("verified_name")}
        )
        return res
    except MetaWhatsAppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/templates/sync")
def sync_whatsapp_templates_from_meta(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Synchronizes WhatsApp templates and their ACTUAL Meta approval statuses from Meta Graph API."""
    try:
        res = sync_meta_templates(db)
        record_audit_log(
            db=db,
            action="whatsapp_templates_synced",
            entity_type="whatsapp_template",
            user_id=current_user.id,
            details=res
        )
        return res
    except MetaWhatsAppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/templates", response_model=List[WhatsAppTemplateResponse])
def get_approved_templates(
    include_all: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    seed_default_meta_templates(db)
    query = db.query(WhatsAppTemplate)
    if not include_all:
        query = query.filter(WhatsAppTemplate.status == "APPROVED")
    return query.order_by(WhatsAppTemplate.synced_from_meta.desc(), WhatsAppTemplate.id.asc()).all()


@router.post("/consent", response_model=ContactConsentResponse, status_code=status.HTTP_201_CREATED)
def record_consent_endpoint(
    consent_in: ContactConsentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return record_contact_consent(db, consent_in)


@router.post("/draft", response_model=WhatsAppMessageResponse, status_code=status.HTTP_201_CREATED)
def draft_whatsapp_endpoint(
    req: WhatsAppDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company = get_company(db, req.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    try:
        msg = create_whatsapp_message(db, company, req)
        return msg
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/approve/{message_id}", response_model=WhatsAppMessageResponse)
def approve_whatsapp_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Restricted to admin/manager. Enforces documented consent and binds immutable content hash."""
    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    try:
        return approve_whatsapp_message_internal(db, msg, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/send/{message_id}", response_model=dict)
def send_whatsapp_endpoint(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    success, msg_text = send_approved_whatsapp_message(db, message_id, current_user.id)
    if not success:
        raise HTTPException(status_code=400, detail=msg_text)
    return {"status": "success", "message": msg_text}


@router.get("/messages", response_model=List[WhatsAppMessageResponse])
def list_whatsapp_messages(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(WhatsAppMessage).order_by(WhatsAppMessage.created_at.desc()).offset(skip).limit(limit).all()


# Meta WhatsApp Webhook Endpoints
@router.get("/webhook")
def meta_webhook_verification(request: Request):
    """Handles Meta webhook verification challenge."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.META_WA_VERIFY_TOKEN:
        return int(challenge) if challenge and challenge.isdigit() else challenge
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@router.post("/webhook")
async def meta_webhook_events(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None)
):
    """Receives inbound delivery updates and messages from Meta Cloud API with HMAC-SHA256 signature verification."""
    raw_body = await request.body()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    success, message = process_incoming_meta_webhook(
        db=db,
        raw_body=raw_body,
        payload=body,
        signature_header=x_hub_signature_256
    )

    if not success:
        if "signature" in message.lower() or "secret" in message.lower():
            raise HTTPException(status_code=403, detail=message)
        raise HTTPException(status_code=400, detail=message)

    return {"status": "received", "detail": message}
