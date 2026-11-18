import base64
import email.utils
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any, Tuple, List
from urllib.parse import urlencode
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import encrypt_secret, decrypt_secret
from app.models.channel import ChannelConnection
from app.models.email import EmailDraft, EmailEvent
from app.models.reply import Reply

logger = logging.getLogger(__name__)

# Least-privilege Google OAuth 2.0 scopes required for sending & reading replies
GMAIL_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailIntegrationError(RuntimeError):
    def __init__(self, message: str, error_code: str = "gmail_error", status_code: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


class GmailReauthRequiredError(GmailIntegrationError):
    def __init__(self, message: str = "Gmail OAuth token expired or revoked. Please reconnect Gmail."):
        super().__init__(message, error_code="reauth_required", status_code=401)


class GmailQuotaExceededError(GmailIntegrationError):
    def __init__(self, message: str = "Gmail API quota or rate limit exceeded. Retry later."):
        super().__init__(message, error_code="rate_limited", status_code=429)


def build_oauth_state(user_id: int, ttl_seconds: int = 600) -> str:
    """Creates an HMAC-SHA256 signed OAuth CSRF state token bound to user_id and expiry."""
    payload = {
        "uid": user_id,
        "nonce": secrets.token_hex(12),
        "exp": int(time.time()) + ttl_seconds,
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("utf-8")
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def verify_oauth_state(state_token: str) -> Optional[int]:
    """Verifies HMAC signature and TTL on OAuth state token; returns user_id or None."""
    if not state_token or "." not in state_token:
        return None
    raw, sig = state_token.rsplit(".", 1)
    expected_sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        padded = raw + "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return int(payload["uid"])
    except Exception:
        return None


def is_gmail_oauth_configured() -> bool:
    return bool((settings.GMAIL_CLIENT_ID or "").strip() and (settings.GMAIL_CLIENT_SECRET or "").strip())


def build_gmail_authorization_url(user_id: int) -> Tuple[str, str]:
    """Builds the Google OAuth 2.0 consent URL with least-privilege scopes and CSRF state."""
    if not is_gmail_oauth_configured():
        raise GmailIntegrationError(
            "Gmail OAuth 2.0 is not configured. Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in environment.",
            error_code="oauth_not_configured",
            status_code=400,
        )
    state = build_oauth_state(user_id)
    params = {
        "client_id": settings.GMAIL_CLIENT_ID.strip(),
        "redirect_uri": settings.GMAIL_REDIRECT_URI.strip(),
        "response_type": "code",
        "scope": " ".join(GMAIL_OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}", state


def get_active_gmail_connection(db: Session) -> Optional[ChannelConnection]:
    return (
        db.query(ChannelConnection)
        .filter(ChannelConnection.channel == "gmail")
        .order_by(ChannelConnection.updated_at.desc())
        .first()
    )


def exchange_code_for_tokens(
    db: Session,
    code: str,
    user_id: int,
    http_client: Optional[httpx.Client] = None,
) -> ChannelConnection:
    """Exchanges Google OAuth authorization code for tokens and persists encrypted credentials."""
    if not is_gmail_oauth_configured():
        raise GmailIntegrationError("Gmail OAuth credentials are not configured.", error_code="oauth_not_configured")

    close_client = http_client is None
    client = http_client or httpx.Client(timeout=12.0)
    try:
        token_resp = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GMAIL_CLIENT_ID.strip(),
                "client_secret": settings.GMAIL_CLIENT_SECRET.strip(),
                "redirect_uri": settings.GMAIL_REDIRECT_URI.strip(),
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            err_body = token_resp.text[:300]
            raise GmailIntegrationError(
                f"Google OAuth token exchange failed (HTTP {token_resp.status_code}): {err_body}",
                error_code="token_exchange_failed",
                status_code=400,
            )

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = int(token_data.get("expires_in", 3600))
        granted_scopes = token_data.get("scope", " ".join(GMAIL_OAUTH_SCOPES))

        if not access_token:
            raise GmailIntegrationError("Google OAuth response did not include an access_token.", error_code="missing_token")

        # Retrieve connected mailbox identity
        account_email = None
        display_name = None
        profile_resp = client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_resp.status_code == 200:
            profile = profile_resp.json()
            account_email = profile.get("email")
            display_name = profile.get("name") or account_email

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=expires_in)

        conn = get_active_gmail_connection(db)
        if not conn:
            conn = ChannelConnection(channel="gmail", connected_by_user_id=user_id)
            db.add(conn)

        conn.account_identifier = account_email or conn.account_identifier
        conn.display_name = display_name or account_email or "Gmail Account"
        conn.status = "connected"
        conn.is_sandbox = False
        conn.encrypted_access_token = encrypt_secret(access_token)
        if refresh_token:
            conn.encrypted_refresh_token = encrypt_secret(refresh_token)
        conn.token_expires_at = expires_at
        conn.scopes = granted_scopes
        conn.last_error = None
        conn.connected_by_user_id = user_id
        conn.updated_at = now

        db.commit()
        db.refresh(conn)
        return conn
    finally:
        if close_client:
            client.close()


def get_valid_gmail_access_token(
    db: Session,
    connection: ChannelConnection,
    http_client: Optional[httpx.Client] = None,
) -> str:
    """Returns a valid decrypted access token, transparently refreshing if expired."""
    if connection.status != "connected":
        raise GmailReauthRequiredError(f"Gmail connection is in '{connection.status}' state.")

    now = datetime.now(timezone.utc)
    expires_at = connection.token_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    access_token = decrypt_secret(connection.encrypted_access_token)
    if access_token and expires_at and expires_at > (now + timedelta(seconds=60)):
        return access_token

    refresh_token = decrypt_secret(connection.encrypted_refresh_token)
    if not refresh_token or not is_gmail_oauth_configured():
        connection.status = "reauth_required"
        connection.last_error = "Access token expired and no refresh token is available."
        db.commit()
        raise GmailReauthRequiredError(connection.last_error)

    close_client = http_client is None
    client = http_client or httpx.Client(timeout=12.0)
    try:
        resp = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.GMAIL_CLIENT_ID.strip(),
                "client_secret": settings.GMAIL_CLIENT_SECRET.strip(),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if resp.status_code != 200:
            err_json = {}
            try:
                err_json = resp.json()
            except Exception:
                pass
            err_code = err_json.get("error", "")
            if resp.status_code in (400, 401) or err_code == "invalid_grant":
                connection.status = "reauth_required"
                connection.last_error = f"Gmail authorization revoked or expired ({err_code or resp.status_code})."
                db.commit()
                raise GmailReauthRequiredError(connection.last_error)
            raise GmailIntegrationError(f"Gmail token refresh failed (HTTP {resp.status_code})", error_code="refresh_failed")

        data = resp.json()
        new_access = data.get("access_token")
        if not new_access:
            raise GmailReauthRequiredError("Token refresh did not return an access_token.")

        expires_in = int(data.get("expires_in", 3600))
        connection.encrypted_access_token = encrypt_secret(new_access)
        connection.token_expires_at = now + timedelta(seconds=expires_in)
        connection.last_error = None
        connection.updated_at = now
        db.commit()
        return new_access
    finally:
        if close_client:
            client.close()


def send_gmail_message(
    db: Session,
    connection: ChannelConnection,
    draft: EmailDraft,
    body_text: str,
    http_client: Optional[httpx.Client] = None,
) -> Tuple[str, Optional[str]]:
    """
    Sends an approved email draft via Gmail API using OAuth 2.0.
    Returns genuine provider (message_id, thread_id) from Google's response.
    Never fabricates a provider message ID.
    """
    access_token = get_valid_gmail_access_token(db, connection, http_client=http_client)

    from_email = connection.account_identifier or settings.SMTP_FROM_EMAIL
    msg = MIMEMultipart("alternative")
    msg["Subject"] = draft.subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{from_email}>"
    msg["To"] = draft.recipient_email
    msg["List-Unsubscribe"] = f"<https://acttrident.ai/opt-out?email={draft.recipient_email}>"

    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if draft.body_html:
        msg.attach(MIMEText(draft.body_html, "html", "utf-8"))

    raw_b64 = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    payload: Dict[str, Any] = {"raw": raw_b64}
    if draft.provider_thread_id:
        payload["threadId"] = draft.provider_thread_id

    close_client = http_client is None
    client = http_client or httpx.Client(timeout=15.0)
    try:
        resp = client.post(
            f"{GMAIL_API_BASE}/messages/send",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code in (401, 403):
            connection.status = "reauth_required"
            connection.last_error = f"Gmail API rejected authorization (HTTP {resp.status_code})."
            db.commit()
            raise GmailReauthRequiredError(connection.last_error)
        if resp.status_code == 429:
            raise GmailQuotaExceededError("Gmail API rate limit or daily quota exceeded.")
        if resp.status_code >= 400:
            raise GmailIntegrationError(
                f"Gmail API send failed (HTTP {resp.status_code}): {resp.text[:300]}",
                error_code=f"http_{resp.status_code}",
                status_code=resp.status_code,
            )

        data = resp.json()
        provider_msg_id = data.get("id")
        provider_thread_id = data.get("threadId")
        if not provider_msg_id:
            raise GmailIntegrationError("Gmail API response did not include a provider message ID.", error_code="missing_provider_id")
        return provider_msg_id, provider_thread_id
    finally:
        if close_client:
            client.close()


def _extract_gmail_plain_body(payload: Dict[str, Any]) -> str:
    """Recursively extracts plain-text body from a Gmail API message payload."""
    if not payload:
        return ""
    mime_type = payload.get("mimeType", "")
    body_data = (payload.get("body") or {}).get("data")
    if mime_type == "text/plain" and body_data:
        padded = body_data + "=" * (-len(body_data) % 4)
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="replace")
    for part in payload.get("parts") or []:
        text = _extract_gmail_plain_body(part)
        if text:
            return text
    if body_data:
        padded = body_data + "=" * (-len(body_data) % 4)
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="replace")
    return ""


def _parse_header_map(headers: List[Dict[str, str]]) -> Dict[str, str]:
    return {h.get("name", "").lower(): h.get("value", "") for h in (headers or [])}


def sync_gmail_replies(
    db: Session,
    connection: ChannelConnection,
    max_results: int = 20,
    http_client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """
    Synchronizes incoming replies and bounce notifications from Gmail API.
    Deduplicates strictly via Reply.provider_message_id and links replies to Company, Lead, Campaign, and Conversation.
    """
    from app.services.reply_classifier_service import ingest_inbound_reply

    access_token = get_valid_gmail_access_token(db, connection, http_client=http_client)
    close_client = http_client is None
    client = http_client or httpx.Client(timeout=15.0)

    synced_replies = 0
    bounces_recorded = 0
    skipped_duplicates = 0

    try:
        list_resp = client.get(
            f"{GMAIL_API_BASE}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"q": "in:inbox newer_than:7d", "maxResults": max_results},
        )
        if list_resp.status_code in (401, 403):
            connection.status = "reauth_required"
            connection.last_error = f"Gmail reply sync unauthorized (HTTP {list_resp.status_code})."
            db.commit()
            raise GmailReauthRequiredError(connection.last_error)
        if list_resp.status_code >= 400:
            raise GmailIntegrationError(f"Gmail list messages failed (HTTP {list_resp.status_code})", error_code="sync_failed")

        messages = list_resp.json().get("messages") or []
        for item in messages:
            msg_id = item.get("id")
            if not msg_id:
                continue

            # Idempotency check: skip already-ingested provider messages
            if db.query(Reply).filter(Reply.provider_message_id == msg_id).first():
                skipped_duplicates += 1
                continue

            msg_resp = client.get(
                f"{GMAIL_API_BASE}/messages/{msg_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"format": "full"},
            )
            if msg_resp.status_code != 200:
                continue

            msg_data = msg_resp.json()
            thread_id = msg_data.get("threadId")
            payload = msg_data.get("payload") or {}
            hdrs = _parse_header_map(payload.get("headers") or [])

            raw_from = hdrs.get("from", "")
            _, sender_email = email.utils.parseaddr(raw_from)
            sender_email = (sender_email or raw_from).strip().lower()
            subject = hdrs.get("subject", "")
            recipient = hdrs.get("to", connection.account_identifier or settings.SMTP_FROM_EMAIL)
            body = _extract_gmail_plain_body(payload) or msg_data.get("snippet", "")

            # Skip self-sent messages
            if connection.account_identifier and sender_email == connection.account_identifier.lower():
                continue

            # Detect provider bounce notifications
            is_bounce = (
                "mailer-daemon" in sender_email
                or "postmaster@" in sender_email
                or "delivery status notification" in subject.lower()
                or "undeliverable" in subject.lower()
            )
            if is_bounce:
                matched_draft = None
                if thread_id:
                    matched_draft = db.query(EmailDraft).filter(EmailDraft.provider_thread_id == thread_id).first()
                if not matched_draft:
                    emails_in_body = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}", body)
                    for candidate in emails_in_body:
                        cand_low = candidate.lower()
                        if cand_low == (connection.account_identifier or "").lower():
                            continue
                        matched_draft = (
                            db.query(EmailDraft)
                            .filter(EmailDraft.recipient_email == cand_low, EmailDraft.approval_status == "sent")
                            .order_by(EmailDraft.sent_at.desc())
                            .first()
                        )
                        if matched_draft:
                            break
                if matched_draft:
                    matched_draft.approval_status = "bounced"
                    matched_draft.error_message = f"Provider bounce notice ({msg_id}): {subject}"
                    db.add(EmailEvent(
                        draft_id=matched_draft.id,
                        event_type="bounced",
                        details=f"Provider bounce message {msg_id}: {body[:400]}"
                    ))
                    db.commit()
                    bounces_recorded += 1
                continue

            # Associate reply with sent EmailDraft thread if available
            matched_draft = None
            if thread_id:
                matched_draft = db.query(EmailDraft).filter(EmailDraft.provider_thread_id == thread_id).first()

            reply = ingest_inbound_reply(
                db=db,
                channel="email",
                sender_identifier=sender_email,
                recipient_identifier=recipient,
                subject=subject,
                message_body=body,
            )
            reply.provider_message_id = msg_id
            reply.provider_thread_id = thread_id
            if matched_draft and matched_draft.campaign_id:
                reply.campaign_id = matched_draft.campaign_id
            db.commit()
            synced_replies += 1

        connection.last_synced_at = datetime.now(timezone.utc)
        connection.last_error = None
        db.commit()

        return {
            "status": "synced",
            "account_email": connection.account_identifier,
            "synced_replies": synced_replies,
            "bounces_recorded": bounces_recorded,
            "skipped_duplicates": skipped_duplicates,
            "last_synced_at": connection.last_synced_at.isoformat(),
        }
    finally:
        if close_client:
            client.close()


def disconnect_gmail_connection(
    db: Session,
    connection: ChannelConnection,
    http_client: Optional[httpx.Client] = None,
) -> ChannelConnection:
    """Revokes OAuth token at Google (best-effort) and permanently wipes stored encrypted tokens."""
    token_to_revoke = decrypt_secret(connection.encrypted_refresh_token) or decrypt_secret(connection.encrypted_access_token)
    if token_to_revoke:
        close_client = http_client is None
        client = http_client or httpx.Client(timeout=8.0)
        try:
            client.post(GOOGLE_REVOKE_URL, params={"token": token_to_revoke})
        except Exception as exc:
            logger.warning(f"Best-effort Google token revocation warning: {exc}")
        finally:
            if close_client:
                client.close()

    connection.status = "disconnected"
    connection.encrypted_access_token = None
    connection.encrypted_refresh_token = None
    connection.token_expires_at = None
    connection.last_error = None
    connection.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(connection)
    return connection


def get_email_channel_status(db: Session) -> Dict[str, Any]:
    """Returns honest, real-time connection status across Gmail OAuth, SMTP fallback, and Mock simulation."""
    conn = get_active_gmail_connection(db)
    smtp_configured = bool(settings.EMAIL_PROVIDER == "smtp" and settings.SMTP_USER and settings.SMTP_PASSWORD)
    gmail_connected = bool(conn and conn.status == "connected" and (conn.encrypted_access_token or conn.encrypted_refresh_token))

    if gmail_connected:
        active_mode = "gmail_oauth"
    elif smtp_configured:
        active_mode = "smtp"
    else:
        active_mode = "mock_simulation"

    return {
        "active_mode": active_mode,
        "is_simulation": active_mode == "mock_simulation",
        "gmail": {
            "oauth_configured": is_gmail_oauth_configured(),
            "redirect_uri": settings.GMAIL_REDIRECT_URI,
            "required_scopes": GMAIL_OAUTH_SCOPES,
            "status": conn.status if conn else "disconnected",
            "account_email": conn.account_identifier if conn else None,
            "display_name": conn.display_name if conn else None,
            "token_expires_at": conn.token_expires_at.isoformat() if (conn and conn.token_expires_at) else None,
            "last_synced_at": conn.last_synced_at.isoformat() if (conn and conn.last_synced_at) else None,
            "last_error": conn.last_error if conn else None,
        },
        "smtp": {
            "configured": smtp_configured,
            "host": settings.SMTP_HOST if smtp_configured else None,
            "from_email": settings.SMTP_FROM_EMAIL if smtp_configured else None,
        },
    }
