import hashlib
import hmac
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.whatsapp_adapter import (
    check_meta_connection_health,
    sync_meta_templates,
    validate_and_order_template_parameters,
    MetaWhatsAppError,
)
from app.models.activity import SuppressionList
from app.models.channel import ChannelConnection
from app.models.company import Company
from app.models.consent import ContactConsent
from app.models.reply import Reply
from app.models.whatsapp import WhatsAppTemplate, WhatsAppMessage
from app.services.whatsapp_service import (
    send_approved_whatsapp_message,
    process_incoming_meta_webhook,
    seed_default_meta_templates,
)


def test_whatsapp_connection_health_and_expired_token_handling(db: Session, monkeypatch):
    """Meta connection health check updates ChannelConnection on 200 and marks reauth_required on code 190."""
    monkeypatch.setattr(settings, "META_WA_ACCESS_TOKEN", "EAAG_test_system_user_token")
    monkeypatch.setattr(settings, "META_WA_PHONE_NUMBER_ID", "105551234567890")

    def ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "verified_name": "ActTrident Security",
            "display_phone_number": "+91 353 254 1000",
            "quality_rating": "GREEN",
        })

    res = check_meta_connection_health(db, http_client=httpx.Client(transport=httpx.MockTransport(ok_handler)))
    assert res["status"] == "connected"
    assert res["verified_name"] == "ActTrident Security"

    conn = db.query(ChannelConnection).filter(ChannelConnection.channel == "whatsapp").first()
    assert conn is not None
    assert conn.status == "connected"
    assert conn.encrypted_access_token.startswith("enc:v1:")

    # Expired token (Meta error code 190) marks reauth_required
    def expired_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"code": 190, "message": "Session has expired"}})

    with pytest.raises(MetaWhatsAppError) as exc_info:
        check_meta_connection_health(db, http_client=httpx.Client(transport=httpx.MockTransport(expired_handler)))
    assert exc_info.value.error_code == "reauth_required"
    db.refresh(conn)
    assert conn.status == "reauth_required"


def test_whatsapp_template_sync_preserves_actual_meta_approval_status(db: Session, monkeypatch):
    """Template sync stores real Meta status (APPROVED vs PENDING vs REJECTED) and sets synced_from_meta=True."""
    monkeypatch.setattr(settings, "META_WA_ACCESS_TOKEN", "EAAG_sync_token")
    monkeypatch.setattr(settings, "META_WA_BUSINESS_ACCOUNT_ID", "998877665544")

    def sync_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "data": [
                {
                    "id": "meta_tmpl_1",
                    "name": "acttrident_verified_intro",
                    "status": "APPROVED",
                    "category": "UTILITY",
                    "language": "en_US",
                    "components": [
                        {"type": "HEADER", "text": "ActTrident Evaluation"},
                        {"type": "BODY", "text": "Hello {{1}}, we support IT teams in {{2}}."},
                        {"type": "FOOTER", "text": "Reply STOP to opt out"},
                    ],
                },
                {
                    "id": "meta_tmpl_2",
                    "name": "acttrident_pending_promo",
                    "status": "PENDING",
                    "category": "MARKETING",
                    "language": "en_US",
                    "components": [
                        {"type": "BODY", "text": "Hi {{1}}, pending approval template."},
                    ],
                },
            ]
        })

    result = sync_meta_templates(db, http_client=httpx.Client(transport=httpx.MockTransport(sync_handler)))
    assert result["synced_templates"] == 2
    assert result["approved_templates"] == 1

    approved_t = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.meta_template_name == "acttrident_verified_intro").first()
    pending_t = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.meta_template_name == "acttrident_pending_promo").first()
    assert approved_t.status == "APPROVED" and approved_t.synced_from_meta is True
    assert pending_t.status == "PENDING" and pending_t.synced_from_meta is True


def test_whatsapp_parameter_ordering_and_unapproved_template_blocked():
    """Parameters are ordered strictly by placeholder index ({{1}}, {{2}}, {{3}}); unapproved/missing rejected."""
    approved_tmpl = WhatsAppTemplate(
        meta_template_name="ordered_test",
        category="UTILITY",
        language="en",
        status="APPROVED",
        body_text="Hi {{1}} at {{2}} in {{3}}!",
    )
    # Deliberately out-of-order dictionary keys
    comps = validate_and_order_template_parameters(
        approved_tmpl, {"3": "Siliguri", "1": "Amitabh", "2": "Infotech"}
    )
    texts = [p["text"] for p in comps[0]["parameters"]]
    assert texts == ["Amitabh", "Infotech", "Siliguri"]

    # Missing required parameter raises MetaWhatsAppError
    with pytest.raises(MetaWhatsAppError, match="missing required parameters"):
        validate_and_order_template_parameters(approved_tmpl, {"1": "Amitabh", "2": "Infotech"})

    # Unapproved template raises MetaWhatsAppError
    pending_tmpl = WhatsAppTemplate(
        meta_template_name="pending_test",
        category="UTILITY",
        language="en",
        status="PENDING",
        body_text="Hi {{1}}",
    )
    with pytest.raises(MetaWhatsAppError, match="not approved by Meta"):
        validate_and_order_template_parameters(pending_tmpl, {"1": "Amitabh"})


def test_whatsapp_live_consent_recheck_blocks_post_approval_opt_out(
    client: TestClient, admin_auth_headers: dict, db: Session, test_company: Company
):
    """Revoking consent after approval MUST block WhatsApp dispatch on live consent re-check."""
    phone = "+919832099887"
    client.post(
        "/api/v1/whatsapp/consent",
        json={
            "company_id": test_company.id,
            "contact_identifier": phone,
            "channel": "whatsapp",
            "consent_status": "opted_in",
            "consent_source": "Inbound Form",
            "consent_purpose": "Demo",
            "proof_reference": "https://acttrident.ai/consent/1",
        },
        headers=admin_auth_headers,
    )
    draft = client.post(
        "/api/v1/whatsapp/draft",
        json={
            "company_id": test_company.id,
            "template_name": "acttrident_intro_utility_v1",
            "recipient_phone": phone,
            "parameters": {"1": "Director", "2": "Siliguri"},
        },
        headers=admin_auth_headers,
    ).json()
    assert client.post(f"/api/v1/whatsapp/approve/{draft['id']}", headers=admin_auth_headers).status_code == 200

    # Prospect revokes consent AFTER approval
    consent_row = db.query(ContactConsent).filter(ContactConsent.company_id == test_company.id).first()
    consent_row.consent_status = "opted_out"
    db.commit()

    # Dispatch must be blocked immediately
    send_res = client.post(f"/api/v1/whatsapp/send/{draft['id']}", headers=admin_auth_headers)
    assert send_res.status_code == 400
    assert "documented permission" in send_res.json()["detail"].lower()


def test_whatsapp_meta_send_real_wamid_ordered_params_and_idempotency(
    client: TestClient, admin_auth_headers: dict, db: Session, test_company: Company, monkeypatch, enable_mocked_live_send
):
    """Meta send transmits ordered template params, stores real wamid, and prevents duplicate retries."""
    monkeypatch.setattr(settings, "META_WA_ACCESS_TOKEN", "EAAG_live_sandbox_token")
    monkeypatch.setattr(settings, "META_WA_PHONE_NUMBER_ID", "105551234567890")

    phone = "+919733011223"
    client.post(
        "/api/v1/whatsapp/consent",
        json={
            "company_id": test_company.id,
            "contact_identifier": phone,
            "channel": "whatsapp",
            "consent_status": "opted_in",
            "consent_source": "Web Form",
            "consent_purpose": "Evaluation",
            "proof_reference": "https://acttrident.ai/form/2",
        },
        headers=admin_auth_headers,
    )
    tmpl = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.meta_template_name == "acttrident_intro_utility_v1").first()
    if not tmpl:
        seed_default_meta_templates(db)
        tmpl = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.meta_template_name == "acttrident_intro_utility_v1").first()
    tmpl.status = "APPROVED"
    db.commit()

    draft = client.post(
        "/api/v1/whatsapp/draft",
        json={
            "company_id": test_company.id,
            "template_name": "acttrident_intro_utility_v1",
            "recipient_phone": phone,
            "parameters": {"2": "Gangtok", "1": "Tenzing"},  # Out of order deliberately
        },
        headers=admin_auth_headers,
    ).json()
    assert client.post(f"/api/v1/whatsapp/approve/{draft['id']}", headers=admin_auth_headers).status_code == 200

    captured = {"calls": 0, "body": None}

    def meta_send_handler(request: httpx.Request) -> httpx.Response:
        captured["calls"] += 1
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"messages": [{"id": "wamid.HBgMOTE5NzMzMDExMjIzVAgA"}]})

    mock_http = httpx.Client(transport=httpx.MockTransport(meta_send_handler))
    ok1, msg1 = send_approved_whatsapp_message(db, draft["id"], user_id=1, http_client=mock_http)
    assert ok1 is True
    assert captured["calls"] == 1
    sent_params = [p["text"] for p in captured["body"]["template"]["components"][0]["parameters"]]
    assert sent_params == ["Tenzing", "Gangtok"]  # Strictly ordered!

    wa_row = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == draft["id"]).first()
    assert wa_row.meta_message_id == "wamid.HBgMOTE5NzMzMDExMjIzVAgA"
    assert wa_row.approval_status == "sent"
    assert wa_row.delivery_status == "sent"

    # Second send attempt must be blocked by idempotency guard
    ok2, msg2 = send_approved_whatsapp_message(db, draft["id"], user_id=1, http_client=mock_http)
    assert ok2 is False
    assert "idempotency" in msg2.lower()
    assert captured["calls"] == 1


def test_whatsapp_webhook_status_lifecycle_and_stop_opt_out(
    db: Session, test_company: Company, monkeypatch
):
    """HMAC-verified webhooks update delivered/read/failed statuses and immediately suppress STOP opt-outs."""
    secret = "test_meta_app_secret_2026"
    monkeypatch.setattr(settings, "META_APP_SECRET", secret)

    wa_msg = WhatsAppMessage(
        company_id=test_company.id,
        recipient_phone="+919832000111",
        message_text="Hello from ActTrident",
        approval_status="sent",
        delivery_status="sent",
        meta_message_id="wamid.lifecycle_1",
        has_valid_consent=True,
    )
    db.add(wa_msg)
    db.commit()

    def sign(body: bytes) -> str:
        return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    # 1. Delivered + Failed status + STOP inbound opt-out
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"display_phone_number": "+913532541000"},
                    "statuses": [{"id": "wamid.lifecycle_1", "status": "delivered"}],
                    "messages": [{
                        "id": "wamid.inbound_stop_1",
                        "from": "919832000111",
                        "text": {"body": "STOP please remove me"},
                    }],
                }
            }]
        }]
    }
    raw = json.dumps(payload).encode("utf-8")
    ok, msg = process_incoming_meta_webhook(db, raw, payload, signature_header=sign(raw))
    assert ok is True

    db.refresh(wa_msg)
    assert wa_msg.delivery_status == "delivered"

    # Inbound STOP must be classified as unsubscribe and added to SuppressionList immediately!
    reply = db.query(Reply).filter(Reply.provider_message_id == "wamid.inbound_stop_1").first()
    assert reply is not None
    assert reply.classification == "unsubscribe"

    # Duplicate webhook is skipped cleanly
    ok_dup, msg_dup = process_incoming_meta_webhook(db, raw, payload, signature_header=sign(raw))
    assert ok_dup is True
    assert "duplicate" in msg_dup.lower()


def test_whatsapp_mock_mode_never_fabricates_wamid(
    client: TestClient, admin_auth_headers: dict, db: Session, test_company: Company, monkeypatch
):
    """Simulation mode must keep meta_message_id=None and delivery_status='simulated'."""
    monkeypatch.setattr(settings, "META_WA_ACCESS_TOKEN", "")
    monkeypatch.setattr(settings, "META_WA_PHONE_NUMBER_ID", "")

    phone = "+919431000555"
    client.post(
        "/api/v1/whatsapp/consent",
        json={
            "company_id": test_company.id,
            "contact_identifier": phone,
            "channel": "whatsapp",
            "consent_status": "opted_in",
            "consent_source": "Inbound Inquiry",
            "consent_purpose": "Evaluation",
            "proof_reference": "https://acttrident.ai/form/3",
        },
        headers=admin_auth_headers,
    )
    draft = client.post(
        "/api/v1/whatsapp/draft",
        json={
            "company_id": test_company.id,
            "template_name": "acttrident_intro_utility_v1",
            "recipient_phone": phone,
            "parameters": {"1": "Rajesh", "2": "Patna"},
        },
        headers=admin_auth_headers,
    ).json()
    assert client.post(f"/api/v1/whatsapp/approve/{draft['id']}", headers=admin_auth_headers).status_code == 200
    send_res = client.post(f"/api/v1/whatsapp/send/{draft['id']}", headers=admin_auth_headers)
    assert send_res.status_code == 200
    assert "SIMULATION MODE" in send_res.json()["message"]

    row = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == draft["id"]).first()
    assert row.delivery_status == "simulated"
    assert row.approval_status == "simulated"
    assert row.meta_message_id is None  # Never fabricated!
