"""
Phase 4A Signed Unsubscribe & RFC 8058 One-Click Opt-Out Service.

Generates tamper-proof, unique HMAC-SHA256 unsubscribe tokens bound to an email address,
builds configurable List-Unsubscribe + List-Unsubscribe-Post headers, and processes
unsubscribe requests idempotently into SuppressionList.
"""
import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import validate_recipient_email_syntax
from app.core.audit import record_audit_log
from app.models.activity import SuppressionList
from app.models.company import Company
from app.models.consent import ContactConsent


def _get_unsubscribe_key() -> str:
    key = (getattr(settings, "UNSUBSCRIBE_SECRET_KEY", "") or "").strip()
    if not key:
        key = (getattr(settings, "APPROVAL_SECRET_KEY", "") or "").strip()
    if not key:
        raise ValueError("CRITICAL: Missing UNSUBSCRIBE_SECRET_KEY / APPROVAL_SECRET_KEY.")
    return key


def generate_unsubscribe_token(email: str, company_id: Optional[int] = None) -> str:
    """Generates a unique, HMAC-SHA256 signed URL-safe token for an email address."""
    normalized_email = validate_recipient_email_syntax(email).lower()
    payload = {
        "e": normalized_email,
        "cid": company_id,
        "n": secrets.token_hex(8),
        "ts": int(datetime.now(timezone.utc).timestamp()),
    }
    raw_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw_json).decode("ascii").rstrip("=")
    key = _get_unsubscribe_key().encode("utf-8")
    sig = hmac.new(key, b64_payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"


def verify_unsubscribe_token(token: str) -> Dict[str, Any]:
    """Verifies an unsubscribe token in constant time and returns its payload."""
    if not token or "." not in token:
        raise ValueError("Invalid unsubscribe token format.")
    b64_payload, provided_sig = token.rsplit(".", 1)
    key = _get_unsubscribe_key().encode("utf-8")
    expected_sig = hmac.new(key, b64_payload.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, provided_sig):
        raise ValueError("Invalid unsubscribe token signature.")

    padded = b64_payload + "=" * (-len(b64_payload) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Corrupted unsubscribe token payload.") from exc

    email = validate_recipient_email_syntax(data.get("e")).lower()
    data["e"] = email
    return data


def build_unsubscribe_url(email: str, company_id: Optional[int] = None) -> str:
    """Constructs a configurable hosted unsubscribe endpoint URL (never hardcoded production domain)."""
    token = generate_unsubscribe_token(email=email, company_id=company_id)
    base = (getattr(settings, "PUBLIC_BASE_URL", "http://localhost:8000") or "http://localhost:8000").rstrip("/")
    api_prefix = getattr(settings, "API_V1_STR", "/api/v1").rstrip("/")
    return f"{base}{api_prefix}/unsubscribe/{token}"


def build_unsubscribe_headers(email: str, company_id: Optional[int] = None) -> Tuple[Dict[str, str], str]:
    """Returns RFC 8058 List-Unsubscribe + List-Unsubscribe-Post headers and the URL."""
    url = build_unsubscribe_url(email=email, company_id=company_id)
    headers = {
        "List-Unsubscribe": f"<{url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    return headers, url


def process_unsubscribe_token(db: Session, token: str, source: str = "hosted_link") -> Dict[str, Any]:
    """Idempotently records the email in SuppressionList and revokes active email consent."""
    payload = verify_unsubscribe_token(token)
    email = payload["e"]
    company_id = payload.get("cid")

    existing = db.query(SuppressionList).filter(SuppressionList.identifier == email).first()
    already_suppressed = existing is not None
    if not existing:
        db.add(SuppressionList(
            identifier=email,
            channel="email",
            reason=f"Unsubscribed via {source} (RFC 8058)",
        ))

    # Update ContactConsent & Lead status if linked
    if company_id:
        consents = db.query(ContactConsent).filter(
            ContactConsent.company_id == company_id,
            ContactConsent.channel == "email",
        ).all()
        for c in consents:
            c.consent_status = "opted_out"
        comp = db.query(Company).filter(Company.id == company_id).first()
        if comp and comp.lead:
            comp.lead.pipeline_status = "opted_out"

    db.commit()
    record_audit_log(
        db=db,
        action="email_unsubscribed",
        entity_type="suppression_list",
        entity_id=email,
        details={"source": source, "already_suppressed": already_suppressed},
    )
    return {
        "status": "unsubscribed",
        "email": email,
        "already_suppressed": already_suppressed,
        "idempotent": True,
    }
