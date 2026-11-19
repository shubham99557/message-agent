"""Phase 5 acceptance tests: Unified ChannelAdapter & Official LinkedIn OAuth 2.0 / Compliant Outreach."""
import httpx
from app.core.config import settings
from app.integrations.channel_adapter import get_channel_adapter
from app.integrations.linkedin_adapter import (
    exchange_linkedin_code_for_tokens,
    generate_linkedin_oauth_state,
)
from app.models.activity import AuditLog, SuppressionList
from app.models.channel import ChannelConnection
from app.models.email import ApprovalRecord
from app.services.linkedin_service import dispatch_approved_linkedin_message


def test_unified_channel_adapter_registry_and_status_endpoint(client, db_session, admin_auth_headers):
    # All three adapters share the exact ChannelAdapter contract
    for name in ("email", "whatsapp", "linkedin"):
        adapter = get_channel_adapter(name)
        assert adapter.channel_name == name
        st = adapter.connection_status(db_session)
        assert st["channel"] == name

    # Recipient validation per channel
    assert get_channel_adapter("email").validate_recipient(db_session, "founder@northbengalcloud.in")[0] is True
    assert get_channel_adapter("email").validate_recipient(db_session, "not-an-email")[0] is False
    assert get_channel_adapter("whatsapp").validate_recipient(db_session, "+919832011001")[0] is True
    assert get_channel_adapter("whatsapp").validate_recipient(db_session, "123")[0] is False
    assert get_channel_adapter("linkedin").validate_recipient(db_session, "https://www.linkedin.com/in/amit-roy")[0] is True
    assert get_channel_adapter("linkedin").validate_recipient(db_session, "https://evil.example.org/in/amit")[0] is False

    # Unified REST status endpoint returns honest status for all 3 channels
    resp = client.get("/api/v1/integrations/channels/status", headers=admin_auth_headers)
    assert resp.status_code == 200
    channels = resp.json()["channels"]
    assert set(channels.keys()) == {"email", "whatsapp", "linkedin"}
    assert channels["linkedin"]["direct_messaging_api_approved"] is False
    assert "scraping" in channels["linkedin"]["compliance_policy"].lower()


def test_linkedin_oauth_start_csrf_validation_token_encryption_and_disconnect(
    client, db_session, admin_auth_headers, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", "li-client-123")
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "li-secret-456")

    # Non-manager sales user cannot start LinkedIn OAuth
    forbidden = client.get("/api/v1/integrations/linkedin/oauth/start", headers=auth_headers)
    assert forbidden.status_code == 403

    # Admin gets official LinkedIn OAuth URL with CSRF state
    start_resp = client.get("/api/v1/integrations/linkedin/oauth/start", headers=admin_auth_headers)
    assert start_resp.status_code == 200
    body = start_resp.json()
    assert body["authorization_url"].startswith("https://www.linkedin.com/oauth/v2/authorization?")
    assert "li-client-123" in body["authorization_url"]
    assert body["state"].startswith("li:")

    # Forged CSRF state is rejected on callback
    bad_cb = client.get("/api/v1/integrations/linkedin/oauth/callback?code=abc&state=li:1:1:x:forged")
    assert bad_cb.status_code == 400

    # Token exchange via httpx.MockTransport stores Fernet-encrypted token (never plaintext)
    def li_oauth_handler(request: httpx.Request) -> httpx.Response:
        if "oauth/v2/accessToken" in str(request.url):
            return httpx.Response(
                200,
                json={"access_token": "li-raw-access-token-secret", "expires_in": 5184000, "scope": "openid profile email"},
            )
        if "v2/userinfo" in str(request.url):
            return httpx.Response(
                200,
                json={"sub": "li_member_99", "name": "Priya Sen", "email": "priya@acttrident.ai"},
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(li_oauth_handler)) as mock_http:
        conn = exchange_linkedin_code_for_tokens(db=db_session, code="valid-auth-code", user_id=1, http_client=mock_http)

    assert conn.status == "connected"
    assert conn.account_identifier == "priya@acttrident.ai"
    assert conn.display_name == "Priya Sen"
    assert conn.encrypted_access_token is not None
    assert "li-raw-access-token-secret" not in conn.encrypted_access_token

    # Status API reports connected profile and NEVER leaks encrypted or plaintext token
    st_resp = client.get("/api/v1/integrations/linkedin/status", headers=admin_auth_headers)
    assert st_resp.status_code == 200
    st = st_resp.json()
    assert st["connected"] is True
    assert st["active_mode"] == "oauth_connected_manual_handoff"
    assert "li-raw-access-token-secret" not in str(st)

    # Disconnect clears encrypted tokens
    disc_resp = client.post("/api/v1/integrations/linkedin/disconnect", headers=admin_auth_headers)
    assert disc_resp.status_code == 200
    db_session.refresh(conn)
    assert conn.status == "disconnected"
    assert conn.encrypted_access_token is None


def test_linkedin_draft_limits_approval_invalidation_and_honest_manual_handoff(
    client, db_session, admin_auth_headers, auth_headers, test_company
):
    # 1. Connection note > 300 chars is rejected
    too_long = client.post(
        "/api/v1/linkedin/draft",
        json={
            "company_id": test_company.id,
            "recipient_profile_url": "https://www.linkedin.com/in/amit-founder",
            "message_type": "connection_note",
            "custom_message": "A" * 305,
        },
        headers=auth_headers,
    )
    assert too_long.status_code == 400
    assert "character limit" in too_long.json()["detail"].lower()

    # 2. Invalid non-LinkedIn URL is rejected
    bad_url = client.post(
        "/api/v1/linkedin/draft",
        json={
            "company_id": test_company.id,
            "recipient_profile_url": "https://notlinkedin.com/in/amit",
            "message_type": "connection_note",
        },
        headers=auth_headers,
    )
    assert bad_url.status_code == 400

    # 3. Valid draft created by sales rep
    draft_resp = client.post(
        "/api/v1/linkedin/draft",
        json={
            "company_id": test_company.id,
            "recipient_name": "Amit Roy",
            "recipient_profile_url": "https://www.linkedin.com/in/amit-founder",
            "message_type": "connection_note",
        },
        headers=auth_headers,
    )
    assert draft_resp.status_code == 201
    draft = draft_resp.json()
    assert draft["approval_status"] == "draft"
    assert len(draft["message_body"]) <= 300

    # 4. Sales rep CANNOT approve or dispatch
    assert client.post(f"/api/v1/linkedin/approve/{draft['id']}", headers=auth_headers).status_code == 403
    assert client.post(f"/api/v1/linkedin/dispatch/{draft['id']}", headers=auth_headers).status_code == 403

    # 5. Admin approves -> records immutable ApprovalRecord
    app_resp = client.post(f"/api/v1/linkedin/approve/{draft['id']}", headers=admin_auth_headers)
    assert app_resp.status_code == 200
    assert app_resp.json()["approval_status"] == "approved"
    rec = db_session.query(ApprovalRecord).filter(
        ApprovalRecord.entity_type == "linkedin_message",
        ApprovalRecord.entity_id == draft["id"],
        ApprovalRecord.action == "approved",
    ).first()
    assert rec is not None

    # 6. Editing an approved draft invalidates approval & updates content hash
    old_hash = app_resp.json()["content_hash"]
    edit_resp = client.put(
        f"/api/v1/linkedin/messages/{draft['id']}",
        json={"message_body": "Hi Amit, would love to share ActTrident's 90-day evaluation for your team."},
        headers=auth_headers,
    )
    assert edit_resp.status_code == 200
    edited = edit_resp.json()
    assert edited["approval_status"] == "draft"
    assert edited["content_hash"] != old_hash

    # Cannot dispatch unapproved draft
    assert client.post(f"/api/v1/linkedin/dispatch/{draft['id']}", headers=admin_auth_headers).status_code == 400

    # Re-approve and dispatch in standard mode (LINKEDIN_MESSAGING_API_APPROVED=False)
    assert client.post(f"/api/v1/linkedin/approve/{draft['id']}", headers=admin_auth_headers).status_code == 200
    disp_resp = client.post(f"/api/v1/linkedin/dispatch/{draft['id']}", headers=admin_auth_headers)
    assert disp_resp.status_code == 200
    disp = disp_resp.json()
    assert disp["status"] == "ready_for_manual_send"
    assert disp["delivery_mode"] == "manual_handoff"
    assert disp["provider_message_id"] is None  # NEVER fabricated!

    # Human confirms manual send -> updates status & audit trail
    conf_resp = client.post(
        f"/api/v1/linkedin/confirm-manual-send/{draft['id']}",
        json={"notes": "Sent from LinkedIn mobile app"},
        headers=auth_headers,
    )
    assert conf_resp.status_code == 200
    confirmed = conf_resp.json()
    assert confirmed["approval_status"] == "manually_sent_confirmed"
    assert confirmed["provider_message_id"] is None
    assert confirmed["sent_at"] is not None
    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "linkedin_manual_send_confirmed",
        AuditLog.entity_id == str(draft["id"]),
    ).first()
    assert audit is not None


def test_linkedin_suppression_blocks_outreach_and_authorized_partner_api_dispatch(
    client, db_session, admin_auth_headers, test_company, monkeypatch
):
    # 1. Suppressed LinkedIn profile is blocked
    suppressed_url = "https://www.linkedin.com/in/opted-out-exec"
    db_session.add(SuppressionList(identifier=suppressed_url, channel="linkedin", reason="explicit_refusal"))
    db_session.commit()

    blocked = client.post(
        "/api/v1/linkedin/draft",
        json={
            "company_id": test_company.id,
            "recipient_profile_url": suppressed_url,
            "message_type": "direct_message",
        },
        headers=admin_auth_headers,
    )
    assert blocked.status_code == 400
    assert "suppression" in blocked.json()["detail"].lower()

    # 2. Authorized Partner API dispatch path via MockTransport (only when explicitly approved & connected)
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", "li-client-123")
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "li-secret-456")
    monkeypatch.setattr(settings, "LINKEDIN_MESSAGING_API_APPROVED", True)
    monkeypatch.setattr(settings, "LINKEDIN_PARTNER_MESSAGING_ENDPOINT", "https://api.linkedin.com/rest/partnerMessages")

    def partner_handler(request: httpx.Request) -> httpx.Response:
        if "oauth/v2/accessToken" in str(request.url):
            return httpx.Response(200, json={"access_token": "partner-oauth-token", "expires_in": 3600})
        if "v2/userinfo" in str(request.url):
            return httpx.Response(200, json={"sub": "partner-user", "name": "Sales Lead", "email": "sales@acttrident.ai"})
        if "rest/partnerMessages" in str(request.url):
            assert request.headers.get("Authorization") == "Bearer partner-oauth-token"
            return httpx.Response(201, json={"id": "urn:li:msg:partner-real-7788"})
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(partner_handler)) as mock_http:
        exchange_linkedin_code_for_tokens(db=db_session, code="partner-code", user_id=1, http_client=mock_http)

        draft = client.post(
            "/api/v1/linkedin/draft",
            json={
                "company_id": test_company.id,
                "recipient_profile_url": "https://www.linkedin.com/in/partner-prospect",
                "message_type": "direct_message",
            },
            headers=admin_auth_headers,
        ).json()
        client.post(f"/api/v1/linkedin/approve/{draft['id']}", headers=admin_auth_headers)

        result = dispatch_approved_linkedin_message(
            db=db_session,
            message_id=draft["id"],
            user_id=1,
            http_client=mock_http,
        )
        assert result["status"] == "sent_via_api"
        assert result["delivery_mode"] == "authorized_partner_api"
        assert result["provider_message_id"] == "urn:li:msg:partner-real-7788"
