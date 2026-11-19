"""
Official LinkedIn OAuth 2.0 & Authorized Partner API Adapter.

COMPLIANCE & SECURITY POLICY:
- Uses ONLY official LinkedIn OAuth 2.0 (authorization_code flow) and approved LinkedIn REST APIs.
- NEVER collects LinkedIn passwords, NEVER extracts browser session cookies (e.g., li_at),
  and NEVER performs headless browser automation or unauthorized scraping.
- LinkedIn's 1:1 Direct Messaging API is restricted to approved LinkedIn Partners. When
  LINKEDIN_MESSAGING_API_APPROVED is False (the honest default for standard apps), approved
  outreach messages use a compliant human-assisted handoff ('ready_for_manual_send') rather
  than fabricating API sends or bypassing LinkedIn's terms.
"""
import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlencode, urlparse
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import encrypt_secret, decrypt_secret
from app.models.channel import ChannelConnection

logger = logging.getLogger("acttrident.linkedin")

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
STATE_TTL_SECONDS = 600


class LinkedInIntegrationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def is_linkedin_oauth_configured() -> bool:
    return bool((settings.LINKEDIN_CLIENT_ID or "").strip() and (settings.LINKEDIN_CLIENT_SECRET or "").strip())


def validate_linkedin_profile_url(url: str) -> Tuple[bool, str]:
    """Validates that a LinkedIn target URL points to an official linkedin.com profile or company page."""
    if not url or not url.strip():
        return False, "LinkedIn profile or company URL is required."
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("https", "http"):
        return False, "LinkedIn URL must start with https://"
    host = (parsed.hostname or "").lower()
    if host not in ("linkedin.com", "www.linkedin.com", "in.linkedin.com"):
        return False, "URL must belong to official linkedin.com domain."
    path = (parsed.path or "").strip("/")
    if not (path.startswith("in/") or path.startswith("company/") or path.startswith("pub/")):
        return False, "LinkedIn URL must point to a member profile (/in/...) or company page (/company/...)."
    return True, "valid"


def _sign_state_payload(payload: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_linkedin_oauth_state(user_id: int) -> str:
    ts = int(time.time())
    nonce = secrets.token_urlsafe(12)
    payload = f"li:{user_id}:{ts}:{nonce}"
    sig = _sign_state_payload(payload)
    return f"{payload}:{sig}"


def verify_linkedin_oauth_state(state: str) -> Optional[int]:
    try:
        parts = state.split(":")
        if len(parts) != 5 or parts[0] != "li":
            return None
        prefix, user_id_str, ts_str, nonce, provided_sig = parts
        payload = f"{prefix}:{user_id_str}:{ts_str}:{nonce}"
        expected_sig = _sign_state_payload(payload)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None
        if abs(int(time.time()) - int(ts_str)) > STATE_TTL_SECONDS:
            return None
        return int(user_id_str)
    except Exception:
        return None


def build_linkedin_authorization_url(user_id: int) -> Tuple[str, str]:
    """Builds official LinkedIn OAuth 2.0 authorization URL with CSRF state protection."""
    if not is_linkedin_oauth_configured():
        raise LinkedInIntegrationError(
            "LinkedIn OAuth 2.0 is not configured. Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in backend environment.",
            status_code=400,
        )
    state = generate_linkedin_oauth_state(user_id)
    scopes = (settings.LINKEDIN_API_SCOPES or "openid profile email").strip()
    params = {
        "response_type": "code",
        "client_id": settings.LINKEDIN_CLIENT_ID.strip(),
        "redirect_uri": settings.LINKEDIN_REDIRECT_URI.strip(),
        "state": state,
        "scope": scopes,
    }
    return f"{LINKEDIN_AUTH_URL}?{urlencode(params)}", state


def get_active_linkedin_connection(db: Session) -> Optional[ChannelConnection]:
    return (
        db.query(ChannelConnection)
        .filter(ChannelConnection.channel == "linkedin")
        .order_by(ChannelConnection.updated_at.desc())
        .first()
    )


def exchange_linkedin_code_for_tokens(
    db: Session,
    code: str,
    user_id: int,
    http_client: Optional[httpx.Client] = None,
) -> ChannelConnection:
    """Exchanges LinkedIn OAuth 2.0 authorization code for tokens and persists them Fernet-encrypted."""
    if not is_linkedin_oauth_configured():
        raise LinkedInIntegrationError("LinkedIn OAuth 2.0 credentials are not configured.", status_code=400)

    close_client = http_client is None
    client = http_client or httpx.Client(timeout=15.0)
    try:
        token_resp = client.post(
            LINKEDIN_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.LINKEDIN_REDIRECT_URI.strip(),
                "client_id": settings.LINKEDIN_CLIENT_ID.strip(),
                "client_secret": settings.LINKEDIN_CLIENT_SECRET.strip(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            raise LinkedInIntegrationError(
                f"LinkedIn token exchange failed (HTTP {token_resp.status_code}).",
                status_code=400,
            )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise LinkedInIntegrationError("LinkedIn token response missing access_token.", status_code=400)

        expires_in = int(token_data.get("expires_in", 5184000))  # LinkedIn standard: 60 days
        refresh_token = token_data.get("refresh_token")
        granted_scopes = token_data.get("scope") or settings.LINKEDIN_API_SCOPES

        # Fetch verified member profile via official OpenID Connect userinfo endpoint
        account_identifier = None
        display_name = None
        profile_resp = client.get(
            LINKEDIN_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_resp.status_code == 200:
            pdata = profile_resp.json()
            account_identifier = pdata.get("email") or pdata.get("sub")
            display_name = pdata.get("name") or f"{pdata.get('given_name', '')} {pdata.get('family_name', '')}".strip()

        now = datetime.now(timezone.utc)
        conn = get_active_linkedin_connection(db)
        if not conn:
            conn = ChannelConnection(channel="linkedin")
            db.add(conn)

        conn.account_identifier = account_identifier or "linkedin-member"
        conn.display_name = display_name or conn.account_identifier
        conn.status = "connected"
        conn.is_sandbox = False
        conn.encrypted_access_token = encrypt_secret(access_token)
        if refresh_token:
            conn.encrypted_refresh_token = encrypt_secret(refresh_token)
        conn.token_expires_at = now + timedelta(seconds=expires_in)
        conn.scopes = granted_scopes
        conn.last_error = None
        conn.last_synced_at = now
        conn.connected_by_user_id = user_id

        db.commit()
        db.refresh(conn)
        return conn
    finally:
        if close_client:
            client.close()


def disconnect_linkedin_connection(db: Session, connection: ChannelConnection) -> ChannelConnection:
    """Clears encrypted LinkedIn OAuth tokens and marks the connection disconnected."""
    connection.encrypted_access_token = None
    connection.encrypted_refresh_token = None
    connection.token_expires_at = None
    connection.status = "disconnected"
    connection.last_error = None
    db.commit()
    db.refresh(connection)
    return connection


def get_linkedin_connection_status(db: Session) -> Dict[str, Any]:
    """Returns honest LinkedIn channel connection and API permission status."""
    conn = get_active_linkedin_connection(db)
    oauth_configured = is_linkedin_oauth_configured()
    messaging_api_approved = bool(
        settings.LINKEDIN_MESSAGING_API_APPROVED
        and (settings.LINKEDIN_PARTNER_MESSAGING_ENDPOINT or "").strip()
    )

    is_connected = False
    status_str = "disconnected"
    account_identifier = None
    display_name = None
    scopes = None
    last_error = None
    token_expires_at = None

    if conn:
        status_str = conn.status
        account_identifier = conn.account_identifier
        display_name = conn.display_name
        scopes = conn.scopes
        last_error = conn.last_error
        token_expires_at = conn.token_expires_at.isoformat() if conn.token_expires_at else None

        if conn.status == "connected" and conn.encrypted_access_token:
            if conn.token_expires_at:
                exp = conn.token_expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp <= datetime.now(timezone.utc):
                    status_str = "reauth_required"
                else:
                    is_connected = True
            else:
                is_connected = True

    if is_connected and messaging_api_approved:
        active_mode = "authorized_partner_api"
        mode_summary = "Connected via Official LinkedIn OAuth 2.0 with approved Partner Messaging API."
    elif is_connected:
        active_mode = "oauth_connected_manual_handoff"
        mode_summary = (
            "Connected via Official LinkedIn OAuth 2.0 (profile verified). Standard LinkedIn apps do not include "
            "direct 1:1 messaging API access; approved drafts use compliant human-assisted handoff."
        )
    else:
        active_mode = "manual_handoff_only"
        mode_summary = (
            "LinkedIn OAuth not connected. Approved drafts can be prepared for compliant human-assisted sending "
            "directly inside LinkedIn (no passwords, cookies, or scraping used)."
        )

    return {
        "channel": "linkedin",
        "status": status_str,
        "connected": is_connected,
        "oauth_configured": oauth_configured,
        "direct_messaging_api_approved": messaging_api_approved,
        "active_mode": active_mode,
        "mode_summary": mode_summary,
        "account_identifier": account_identifier,
        "display_name": display_name,
        "scopes": scopes,
        "token_expires_at": token_expires_at,
        "last_error": last_error,
        "compliance_policy": "Official OAuth 2.0 & Partner API only — password collection, cookie extraction, and scraping are strictly prohibited.",
    }


def dispatch_via_authorized_linkedin_partner_api(
    db: Session,
    connection: ChannelConnection,
    recipient_profile_url: str,
    message_type: str,
    message_body: str,
    idempotency_key: str,
    http_client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """
    Sends a LinkedIn message ONLY when LINKEDIN_MESSAGING_API_APPROVED=True,
    an official LINKEDIN_PARTNER_MESSAGING_ENDPOINT is configured, and a valid OAuth token exists.
    Never fabricates a provider message ID.
    """
    if not settings.LINKEDIN_MESSAGING_API_APPROVED or not (settings.LINKEDIN_PARTNER_MESSAGING_ENDPOINT or "").strip():
        raise LinkedInIntegrationError(
            "Direct LinkedIn Messaging API is not approved/configured for this app. Use compliant manual handoff.",
            status_code=400,
        )

    access_token = decrypt_secret(connection.encrypted_access_token) if connection.encrypted_access_token else None
    if not access_token:
        connection.status = "reauth_required"
        db.commit()
        raise LinkedInIntegrationError("LinkedIn OAuth access token missing or expired; reconnect required.", status_code=401)

    close_client = http_client is None
    client = http_client or httpx.Client(timeout=15.0)
    try:
        resp = client.post(
            settings.LINKEDIN_PARTNER_MESSAGING_ENDPOINT.strip(),
            json={
                "recipient_profile_url": recipient_profile_url,
                "message_type": message_type,
                "body": message_body,
                "idempotency_key": idempotency_key,
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code == 401:
            connection.status = "reauth_required"
            connection.last_error = "LinkedIn OAuth token rejected (HTTP 401)"
            db.commit()
            raise LinkedInIntegrationError("LinkedIn OAuth token rejected (HTTP 401). Please reconnect.", status_code=401)
        if resp.status_code not in (200, 201, 202):
            raise LinkedInIntegrationError(
                f"Authorized LinkedIn Partner API returned HTTP {resp.status_code}: {resp.text[:200]}",
                status_code=502,
            )
        data = resp.json() if resp.content else {}
        provider_id = data.get("id") or data.get("message_id") or resp.headers.get("x-restli-id")
        if not provider_id:
            raise LinkedInIntegrationError("LinkedIn Partner API response did not include a provider message ID.", status_code=502)
        return {
            "provider_message_id": str(provider_id),
            "raw_status": resp.status_code,
        }
    finally:
        if close_client:
            client.close()
