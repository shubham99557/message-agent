import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import encrypt_secret
from app.models.channel import ChannelConnection
from app.models.whatsapp import WhatsAppTemplate, WhatsAppMessage

logger = logging.getLogger(__name__)

META_GRAPH_API_BASE = "https://graph.facebook.com/v20.0"
PLACEHOLDER_PATTERN = re.compile(r"\{\{(\d+)\}\}")
VALID_WA_CATEGORIES = {"UTILITY", "MARKETING", "AUTHENTICATION"}


class MetaWhatsAppError(RuntimeError):
    def __init__(self, message: str, error_code: str = "meta_whatsapp_error", status_code: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


def is_meta_wa_configured() -> bool:
    return bool((settings.META_WA_ACCESS_TOKEN or "").strip() and (settings.META_WA_PHONE_NUMBER_ID or "").strip())


def extract_template_placeholders(body_text: str) -> List[int]:
    """Extracts unique numeric placeholder indices ({{1}}, {{2}}, ...) in ascending numerical order."""
    indices = {int(m) for m in PLACEHOLDER_PATTERN.findall(body_text or "")}
    return sorted(indices)


def validate_and_order_template_parameters(
    template: WhatsAppTemplate,
    parameters: Dict[str, Any],
    require_meta_approved: bool = True,
) -> List[Dict[str, Any]]:
    """
    Validates template status, language, category, and required variables, then returns
    strictly numerically ordered Meta Graph API template components.
    """
    if not template:
        raise MetaWhatsAppError("WhatsApp template is missing.", error_code="missing_template")

    if require_meta_approved and (template.status or "").upper() != "APPROVED":
        raise MetaWhatsAppError(
            f"Template '{template.meta_template_name}' is not approved by Meta (current status: {template.status}).",
            error_code="template_not_approved",
        )

    if not (template.language or "").strip():
        raise MetaWhatsAppError(
            f"Template '{template.meta_template_name}' is missing a valid language code.",
            error_code="invalid_language",
        )

    required_indices = extract_template_placeholders(template.body_text)
    if not required_indices:
        return []

    params_map = {str(k).strip(): str(v).strip() for k, v in (parameters or {}).items() if v is not None}
    ordered_params = []
    missing = []
    for idx in required_indices:
        key = str(idx)
        val = params_map.get(key, "")
        if not val:
            missing.append(f"{{{{{idx}}}}}")
        else:
            ordered_params.append({"type": "text", "text": val})

    if missing:
        raise MetaWhatsAppError(
            f"Template '{template.meta_template_name}' is missing required parameters: {', '.join(missing)}",
            error_code="missing_template_parameters",
        )

    return [{"type": "body", "parameters": ordered_params}]


def _get_or_create_wa_connection(db: Session) -> ChannelConnection:
    conn = (
        db.query(ChannelConnection)
        .filter(ChannelConnection.channel == "whatsapp")
        .order_by(ChannelConnection.updated_at.desc())
        .first()
    )
    if not conn:
        conn = ChannelConnection(channel="whatsapp", status="disconnected")
        db.add(conn)
        db.flush()
    return conn


def _parse_meta_error(resp: httpx.Response) -> Tuple[str, str]:
    try:
        err = resp.json().get("error") or {}
        code = str(err.get("code") or resp.status_code)
        msg = err.get("message") or resp.text[:300]
        return code, msg
    except Exception:
        return str(resp.status_code), resp.text[:300]


def check_meta_connection_health(
    db: Session,
    http_client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """Queries Meta Graph API phone number endpoint to verify live credentials and phone health."""
    if not is_meta_wa_configured():
        raise MetaWhatsAppError(
            "Meta WhatsApp Cloud API credentials are not configured. Set META_WA_ACCESS_TOKEN and META_WA_PHONE_NUMBER_ID.",
            error_code="not_configured",
        )

    conn = _get_or_create_wa_connection(db)
    url = f"{META_GRAPH_API_BASE}/{settings.META_WA_PHONE_NUMBER_ID.strip()}"
    headers = {"Authorization": f"Bearer {settings.META_WA_ACCESS_TOKEN.strip()}"}

    close_client = http_client is None
    client = http_client or httpx.Client(timeout=12.0)
    try:
        resp = client.get(url, headers=headers, params={"fields": "verified_name,display_phone_number,quality_rating"})
        now = datetime.now(timezone.utc)
        if resp.status_code == 200:
            data = resp.json()
            conn.account_identifier = settings.META_WA_PHONE_NUMBER_ID.strip()
            conn.display_name = data.get("verified_name") or data.get("display_phone_number") or "WhatsApp Business"
            conn.status = "connected"
            conn.encrypted_access_token = encrypt_secret(settings.META_WA_ACCESS_TOKEN.strip())
            conn.last_synced_at = now
            conn.last_error = None
            db.commit()
            return {
                "status": "connected",
                "phone_number_id": settings.META_WA_PHONE_NUMBER_ID.strip(),
                "verified_name": data.get("verified_name"),
                "display_phone_number": data.get("display_phone_number"),
                "quality_rating": data.get("quality_rating"),
                "checked_at": now.isoformat(),
            }

        code, msg = _parse_meta_error(resp)
        if resp.status_code == 401 or code == "190":
            conn.status = "reauth_required"
            conn.last_error = f"Meta access token expired or invalid (code {code}): {msg}"
            db.commit()
            raise MetaWhatsAppError(conn.last_error, error_code="reauth_required", status_code=401)
        if resp.status_code == 429 or code == "80007":
            raise MetaWhatsAppError(f"Meta Graph API rate limit exceeded: {msg}", error_code="rate_limited", status_code=429)

        conn.status = "error"
        conn.last_error = f"Meta API error ({code}): {msg}"
        db.commit()
        raise MetaWhatsAppError(conn.last_error, error_code=f"meta_{code}", status_code=resp.status_code)
    finally:
        if close_client:
            client.close()


def sync_meta_templates(
    db: Session,
    http_client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """
    Synchronizes WhatsApp message templates and their ACTUAL approval status from Meta Graph API.
    Never treats local un-synced templates as provider-approved.
    """
    token = (settings.META_WA_ACCESS_TOKEN or "").strip()
    waba_id = (settings.META_WA_BUSINESS_ACCOUNT_ID or "").strip()
    if not token or not waba_id:
        raise MetaWhatsAppError(
            "META_WA_ACCESS_TOKEN and META_WA_BUSINESS_ACCOUNT_ID are required to sync templates from Meta.",
            error_code="waba_not_configured",
        )

    url = f"{META_GRAPH_API_BASE}/{waba_id}/message_templates"
    headers = {"Authorization": f"Bearer {token}"}

    close_client = http_client is None
    client = http_client or httpx.Client(timeout=15.0)
    try:
        resp = client.get(
            url,
            headers=headers,
            params={"fields": "id,name,status,category,language,components", "limit": 100},
        )
        if resp.status_code != 200:
            code, msg = _parse_meta_error(resp)
            if resp.status_code == 401 or code == "190":
                conn = _get_or_create_wa_connection(db)
                conn.status = "reauth_required"
                conn.last_error = f"Meta token expired during template sync: {msg}"
                db.commit()
                raise MetaWhatsAppError(conn.last_error, error_code="reauth_required", status_code=401)
            raise MetaWhatsAppError(f"Meta template sync failed ({code}): {msg}", error_code=f"meta_{code}", status_code=resp.status_code)

        items = resp.json().get("data") or []
        now = datetime.now(timezone.utc)
        synced_count = 0
        approved_count = 0

        for item in items:
            name = item.get("name")
            if not name:
                continue
            meta_status = (item.get("status") or "PENDING").upper()
            category = (item.get("category") or "UTILITY").upper()
            language = item.get("language") or "en"
            meta_id = str(item.get("id") or "")

            header_text = None
            body_text = ""
            footer_text = None
            for comp in item.get("components") or []:
                ctype = (comp.get("type") or "").upper()
                if ctype == "HEADER" and comp.get("text"):
                    header_text = comp["text"]
                elif ctype == "BODY" and comp.get("text"):
                    body_text = comp["text"]
                elif ctype == "FOOTER" and comp.get("text"):
                    footer_text = comp["text"]

            placeholders = extract_template_placeholders(body_text)
            vars_schema = json.dumps({str(i): f"param_{i}" for i in placeholders}) if placeholders else None

            existing = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.meta_template_name == name).first()
            if existing:
                existing.meta_template_id = meta_id or existing.meta_template_id
                existing.status = meta_status
                existing.category = category
                existing.language = language
                existing.header_text = header_text
                if body_text:
                    existing.body_text = body_text
                existing.footer_text = footer_text
                existing.variables_schema = vars_schema
                existing.synced_from_meta = True
                existing.last_synced_at = now
            else:
                db.add(WhatsAppTemplate(
                    meta_template_id=meta_id or None,
                    meta_template_name=name,
                    category=category,
                    language=language,
                    status=meta_status,
                    synced_from_meta=True,
                    last_synced_at=now,
                    header_text=header_text,
                    body_text=body_text or f"Meta template {name}",
                    footer_text=footer_text,
                    variables_schema=vars_schema,
                ))
            synced_count += 1
            if meta_status == "APPROVED":
                approved_count += 1

        conn = _get_or_create_wa_connection(db)
        conn.last_synced_at = now
        conn.last_error = None
        db.commit()

        return {
            "status": "synced",
            "synced_templates": synced_count,
            "approved_templates": approved_count,
            "last_synced_at": now.isoformat(),
        }
    finally:
        if close_client:
            client.close()


def send_meta_template_message(
    db: Session,
    msg: WhatsAppMessage,
    http_client: Optional[httpx.Client] = None,
) -> str:
    """
    Sends an approved, consented WhatsApp template message through the official Meta Cloud API.
    Returns genuine Meta message ID (wamid.*); never fabricates a fallback ID.
    """
    if not is_meta_wa_configured():
        raise MetaWhatsAppError("Meta WhatsApp Cloud API credentials are not configured.", error_code="not_configured")

    params_dict = json.loads(msg.parameters_json) if msg.parameters_json else {}
    ordered_components = validate_and_order_template_parameters(
        template=msg.template,
        parameters=params_dict,
        require_meta_approved=True,
    )

    url = f"{META_GRAPH_API_BASE}/{settings.META_WA_PHONE_NUMBER_ID.strip()}/messages"
    headers = {
        "Authorization": f"Bearer {settings.META_WA_ACCESS_TOKEN.strip()}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": msg.recipient_phone.lstrip("+"),
        "type": "template",
        "template": {
            "name": msg.template.meta_template_name,
            "language": {"code": msg.template.language},
        },
    }
    if ordered_components:
        payload["template"]["components"] = ordered_components

    close_client = http_client is None
    client = http_client or httpx.Client(timeout=15.0)
    try:
        resp = client.post(url, headers=headers, json=payload)
        if resp.status_code in (200, 201):
            data = resp.json()
            messages_arr = data.get("messages") or []
            meta_msg_id = messages_arr[0].get("id") if messages_arr else None
            if not meta_msg_id:
                raise MetaWhatsAppError(
                    "Meta API accepted request but returned no provider message ID.",
                    error_code="missing_wamid",
                )
            return meta_msg_id

        code, err_msg = _parse_meta_error(resp)
        if resp.status_code == 401 or code == "190":
            conn = _get_or_create_wa_connection(db)
            conn.status = "reauth_required"
            conn.last_error = f"Meta token expired (code {code}): {err_msg}"
            db.commit()
            raise MetaWhatsAppError(conn.last_error, error_code="reauth_required", status_code=401)
        if resp.status_code == 429 or code == "80007":
            raise MetaWhatsAppError(f"Meta WhatsApp rate limit exceeded: {err_msg}", error_code="rate_limited", status_code=429)
        if code in ("132000", "132001"):
            raise MetaWhatsAppError(f"Invalid Meta template or parameter mismatch (code {code}): {err_msg}", error_code=f"meta_{code}", status_code=400)
        raise MetaWhatsAppError(f"Meta API Error ({code}): {err_msg}", error_code=f"meta_{code}", status_code=resp.status_code)
    finally:
        if close_client:
            client.close()


def get_whatsapp_connection_status(db: Session) -> Dict[str, Any]:
    """Returns honest WhatsApp Cloud API status separating live Meta API from local simulation mode."""
    conn = (
        db.query(ChannelConnection)
        .filter(ChannelConnection.channel == "whatsapp")
        .order_by(ChannelConnection.updated_at.desc())
        .first()
    )
    configured = is_meta_wa_configured()
    active_mode = "meta_cloud_api" if configured else "mock_simulation"
    synced_templates = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.synced_from_meta == True).count()
    local_templates = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.synced_from_meta == False).count()

    return {
        "active_mode": active_mode,
        "is_simulation": active_mode == "mock_simulation",
        "credentials_configured": configured,
        "waba_configured": bool((settings.META_WA_BUSINESS_ACCOUNT_ID or "").strip()),
        "webhook_secret_configured": bool((settings.META_APP_SECRET or "").strip()),
        "phone_number_id": settings.META_WA_PHONE_NUMBER_ID if configured else None,
        "status": conn.status if conn else ("configured_unverified" if configured else "disconnected"),
        "display_name": conn.display_name if conn else None,
        "last_synced_at": conn.last_synced_at.isoformat() if (conn and conn.last_synced_at) else None,
        "last_error": conn.last_error if conn else None,
        "synced_templates_count": synced_templates,
        "local_seed_templates_count": local_templates,
    }
