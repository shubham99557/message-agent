import base64
import json
from datetime import datetime, timezone, timedelta
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import encrypt_secret, decrypt_secret
from app.integrations.gmail_adapter import (
    build_oauth_state,
    verify_oauth_state,
    exchange_code_for_tokens,
    get_valid_gmail_access_token,
    sync_gmail_replies,
    disconnect_gmail_connection,
    GmailReauthRequiredError,
    GMAIL_OAUTH_SCOPES,
)
from app.models.channel import ChannelConnection
from app.models.company import Company
from app.models.email import EmailDraft, EmailEvent, EmailSendAttempt
from app.models.reply import Reply
from app.services.email_sender_service import send_approved_email


def test_gmail_oauth_start_and_csrf_state_validation(client: TestClient, admin_auth_headers: dict, monkeypatch):
    """OAuth start generates least-privilege Google URL with HMAC-signed CSRF state; tampered state rejected."""
    monkeypatch.setattr(settings, "GMAIL_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GMAIL_CLIENT_SECRET", "test-client-secret-xyz")

    res = client.get("/api/v1/integrations/gmail/oauth/start", headers=admin_auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "accounts.google.com/o/oauth2/v2/auth" in data["authorization_url"]
    assert "gmail.send" in data["authorization_url"]
    assert "gmail.readonly" in data["authorization_url"]
    assert "mail.google.com" not in data["authorization_url"]  # No over-privileged full-access scope!
    assert data["scopes"] == GMAIL_OAUTH_SCOPES

    # Valid state verifies cleanly
    uid = verify_oauth_state(data["state"])
    assert uid is not None

    # Tampered state fails callback with 400
    cb_bad = client.get("/api/v1/integrations/gmail/oauth/callback?code=abc&state=tampered.signature")
    assert cb_bad.status_code == 400
    assert "state" in cb_bad.json()["detail"].lower()


def test_gmail_oauth_exchange_encrypts_tokens_and_reports_honest_status(
    client: TestClient, admin_auth_headers: dict, db: Session, monkeypatch
):
    """Token exchange persists Fernet-encrypted OAuth tokens and never exposes raw tokens via status API."""
    monkeypatch.setattr(settings, "GMAIL_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GMAIL_CLIENT_SECRET", "test-client-secret")

    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth2.googleapis.com/token" in str(request.url):
            return httpx.Response(200, json={
                "access_token": "ya29.real_test_access_token",
                "refresh_token": "1//0g_real_test_refresh_token",
                "expires_in": 3600,
                "scope": " ".join(GMAIL_OAUTH_SCOPES),
            })
        if "oauth2/v2/userinfo" in str(request.url):
            return httpx.Response(200, json={
                "email": "outreach-test@acttrident.ai",
                "name": "ActTrident Outreach Desk",
            })
        return httpx.Response(404)

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    conn = exchange_code_for_tokens(db=db, code="auth-code-123", user_id=1, http_client=mock_http)

    assert conn.status == "connected"
    assert conn.account_identifier == "outreach-test@acttrident.ai"
    assert conn.encrypted_access_token.startswith("enc:v1:")
    assert conn.encrypted_refresh_token.startswith("enc:v1:")
    assert "ya29.real_test_access_token" not in conn.encrypted_access_token
    assert decrypt_secret(conn.encrypted_access_token) == "ya29.real_test_access_token"

    # Status API reports gmail_oauth cleanly with zero raw tokens
    status_res = client.get("/api/v1/integrations/gmail/status", headers=admin_auth_headers)
    assert status_res.status_code == 200
    sdata = status_res.json()
    assert sdata["active_mode"] == "gmail_oauth"
    assert sdata["is_simulation"] is False
    assert sdata["gmail"]["account_email"] == "outreach-test@acttrident.ai"
    assert "ya29.real_test_access_token" not in json.dumps(sdata)
    assert "1//0g_real_test_refresh_token" not in json.dumps(sdata)


def test_gmail_token_refresh_and_revoked_reauth_handling(db: Session, monkeypatch):
    """Expired token automatically refreshes; invalid_grant marks connection reauth_required."""
    monkeypatch.setattr(settings, "GMAIL_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GMAIL_CLIENT_SECRET", "test-client-secret")

    conn = ChannelConnection(
        channel="gmail",
        account_identifier="sales-desk@acttrident.ai",
        status="connected",
        encrypted_access_token=encrypt_secret("expired_token"),
        encrypted_refresh_token=encrypt_secret("valid_refresh_token"),
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)

    # 1. Successful refresh
    def ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "ya29.fresh_rotated_token", "expires_in": 3600})

    fresh = get_valid_gmail_access_token(db, conn, http_client=httpx.Client(transport=httpx.MockTransport(ok_handler)))
    assert fresh == "ya29.fresh_rotated_token"
    assert decrypt_secret(conn.encrypted_access_token) == "ya29.fresh_rotated_token"

    # 2. Force expiry + simulate revoked token (invalid_grant)
    conn.token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    def revoked_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Token has been revoked."})

    with pytest.raises(GmailReauthRequiredError):
        get_valid_gmail_access_token(db, conn, http_client=httpx.Client(transport=httpx.MockTransport(revoked_handler)))

    db.refresh(conn)
    assert conn.status == "reauth_required"
    assert "invalid_grant" in (conn.last_error or "")


def test_gmail_send_approved_email_provider_id_attempts_and_idempotency(
    client: TestClient, admin_auth_headers: dict, db: Session, test_company: Company
):
    """Gmail send persists real Google message/thread IDs, logs EmailSendAttempt, and prevents duplicate retries."""
    conn = ChannelConnection(
        channel="gmail",
        account_identifier="outreach@acttrident.ai",
        status="connected",
        encrypted_access_token=encrypt_secret("ya29.live_sandbox_token"),
        encrypted_refresh_token=encrypt_secret("1//refresh"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(conn)
    db.commit()

    draft_id = client.post(
        "/api/v1/emails/generate",
        json={"company_id": test_company.id, "tone": "Friendly professional"},
        headers=admin_auth_headers
    ).json()["id"]
    assert client.post(f"/api/v1/approvals/approve/{draft_id}", headers=admin_auth_headers).status_code == 200

    api_calls = {"count": 0}

    def gmail_send_handler(request: httpx.Request) -> httpx.Response:
        api_calls["count"] += 1
        return httpx.Response(200, json={"id": "gmail_msg_998877", "threadId": "gmail_thr_554433"})

    mock_http = httpx.Client(transport=httpx.MockTransport(gmail_send_handler))
    res1 = send_approved_email(db, draft_id, user_id=1, http_client=mock_http)
    assert res1.status == "sent"
    assert res1.provider == "gmail"
    assert api_calls["count"] == 1

    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    assert draft.approval_status == "sent"  # Not marked 'delivered' until provider confirms
    assert draft.provider_message_id == "gmail_msg_998877"
    assert draft.provider_thread_id == "gmail_thr_554433"

    # Retry attempt MUST be blocked by idempotency guard without issuing a second Gmail API POST
    res2 = send_approved_email(db, draft_id, user_id=1, http_client=mock_http)
    assert res2.status == "duplicate_blocked"
    assert api_calls["count"] == 1

    # Verify separate EmailSendAttempt record via API
    attempts_res = client.get(f"/api/v1/emails/drafts/{draft_id}/attempts", headers=admin_auth_headers)
    assert attempts_res.status_code == 200
    attempts = attempts_res.json()
    assert len(attempts) == 1
    assert attempts[0]["outcome"] == "sent"
    assert attempts[0]["provider_message_id"] == "gmail_msg_998877"


def test_gmail_reply_sync_deduplication_and_bounce_detection(
    db: Session, test_company: Company
):
    """Gmail sync ingests prospect replies once (deduped), links thread/campaign, and marks bounces."""
    conn = ChannelConnection(
        channel="gmail",
        account_identifier="outreach@acttrident.ai",
        status="connected",
        encrypted_access_token=encrypt_secret("ya29.sync_token"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(conn)

    # Seed two sent drafts: one receives a reply, the other bounces
    sent_reply_draft = EmailDraft(
        company_id=test_company.id,
        recipient_email=test_company.public_email,
        subject="ActTrident 90-Day Evaluation",
        body_text="Hello",
        body_html="<p>Hello</p>",
        approval_status="sent",
        provider="gmail",
        provider_message_id="msg_orig_1",
        provider_thread_id="thr_prospect_1",
    )
    sent_bounce_draft = EmailDraft(
        company_id=test_company.id,
        recipient_email="invalid-address@bounced.example.com",
        subject="ActTrident Evaluation",
        body_text="Hello",
        body_html="<p>Hello</p>",
        approval_status="sent",
        provider="gmail",
        provider_message_id="msg_orig_2",
        provider_thread_id="thr_bounce_2",
    )
    db.add_all([sent_reply_draft, sent_bounce_draft])
    db.commit()

    reply_body_b64 = base64.urlsafe_b64encode(b"Thanks! We are interested in scheduling a product demonstration.").decode()
    bounce_body_b64 = base64.urlsafe_b64encode(b"550 5.1.1 Address not found: invalid-address@bounced.example.com").decode()

    def sync_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/messages") or "/messages?" in url:
            return httpx.Response(200, json={"messages": [{"id": "in_msg_1"}, {"id": "in_bounce_2"}]})
        if "/messages/in_msg_1" in url:
            return httpx.Response(200, json={
                "id": "in_msg_1",
                "threadId": "thr_prospect_1",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [
                        {"name": "From", "value": f"Director <{test_company.public_email}>"},
                        {"name": "To", "value": "outreach@acttrident.ai"},
                        {"name": "Subject", "value": "Re: ActTrident 90-Day Evaluation"},
                    ],
                    "body": {"data": reply_body_b64},
                },
            })
        if "/messages/in_bounce_2" in url:
            return httpx.Response(200, json={
                "id": "in_bounce_2",
                "threadId": "thr_bounce_2",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [
                        {"name": "From", "value": "Mail Delivery Subsystem <mailer-daemon@googlemail.com>"},
                        {"name": "To", "value": "outreach@acttrident.ai"},
                        {"name": "Subject", "value": "Delivery Status Notification (Failure)"},
                    ],
                    "body": {"data": bounce_body_b64},
                },
            })
        return httpx.Response(404)

    mock_http = httpx.Client(transport=httpx.MockTransport(sync_handler))
    sync1 = sync_gmail_replies(db=db, connection=conn, http_client=mock_http)
    assert sync1["synced_replies"] == 1
    assert sync1["bounces_recorded"] == 1

    # Verify reply saved with provider_message_id and classified properly
    reply = db.query(Reply).filter(Reply.provider_message_id == "in_msg_1").first()
    assert reply is not None
    assert reply.classification == "requests_demonstration"
    assert reply.provider_thread_id == "thr_prospect_1"

    # Verify bounced draft transitioned to bounced + bounced EmailEvent logged
    db.refresh(sent_bounce_draft)
    assert sent_bounce_draft.approval_status == "bounced"
    assert db.query(EmailEvent).filter(EmailEvent.draft_id == sent_bounce_draft.id, EmailEvent.event_type == "bounced").count() == 1

    # Second sync skips duplicate reply cleanly
    sync2 = sync_gmail_replies(db=db, connection=conn, http_client=mock_http)
    assert sync2["synced_replies"] == 0
    assert sync2["skipped_duplicates"] == 1


def test_provider_delivery_event_and_mock_no_fabricated_provider_id(
    client: TestClient, admin_auth_headers: dict, db: Session, test_company: Company
):
    """Mock sends never fabricate provider_message_id; provider events update real sent drafts only."""
    # 1. Mock send
    draft_id = client.post(
        "/api/v1/emails/generate",
        json={"company_id": test_company.id, "tone": "Formal"},
        headers=admin_auth_headers
    ).json()["id"]
    client.post(f"/api/v1/approvals/approve/{draft_id}", headers=admin_auth_headers)
    send_res = client.post(f"/api/v1/emails/send/{draft_id}", headers=admin_auth_headers)
    assert send_res.status_code == 200
    assert send_res.json()["status"] == "simulated"

    sim_draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    assert sim_draft.provider_message_id is None  # Never fabricated in mock mode!
    assert sim_draft.approval_status == "simulated"

    # 2. Real sent draft receives provider-confirmed delivery event
    real_draft = EmailDraft(
        company_id=test_company.id,
        recipient_email=test_company.public_email,
        subject="Real Sent Subject",
        body_text="Real Body",
        body_html="<p>Real Body</p>",
        approval_status="sent",
        provider="gmail",
        provider_message_id="real_gmail_id_101",
    )
    db.add(real_draft)
    db.commit()

    ev_res = client.post(
        "/api/v1/emails/events/provider",
        json={"provider_message_id": "real_gmail_id_101", "event_type": "delivered", "details": "Confirmed by provider"},
        headers=admin_auth_headers
    )
    assert ev_res.status_code == 200
    assert ev_res.json()["approval_status"] == "delivered"


def test_gmail_disconnect_wipes_tokens(db: Session):
    """Disconnecting Gmail wipes encrypted access/refresh tokens and sets status to disconnected."""
    conn = ChannelConnection(
        channel="gmail",
        account_identifier="revoke-me@acttrident.ai",
        status="connected",
        encrypted_access_token=encrypt_secret("ya29.to_revoke"),
        encrypted_refresh_token=encrypt_secret("1//to_revoke"),
    )
    db.add(conn)
    db.commit()

    mock_http = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200)))
    disconnect_gmail_connection(db, conn, http_client=mock_http)

    assert conn.status == "disconnected"
    assert conn.encrypted_access_token is None
    assert conn.encrypted_refresh_token is None
