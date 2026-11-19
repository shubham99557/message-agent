import hmac
import hashlib
import json
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, RefreshToken
from app.models.company import Company
from app.models.email import EmailDraft, EmailEvent
from app.models.whatsapp import WhatsAppTemplate, WhatsAppMessage, WebhookEvent
from app.core.config import Settings, settings
from app.core.security import compute_content_hash, create_access_token


def test_public_registration_privilege_escalation_blocked(client: TestClient, db: Session):
    """Vulnerability SEC-01: Public registration must never allow administrator or manager role assignment."""
    payload = {
        "email": "hacker@example.com",
        "full_name": "Rogue Agent",
        "password": "Password123!",
        "role": "admin"  # Malicious attempt to self-promote to admin
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "sales_rep", "Public registration must force role to sales_rep"

    # Verify directly in DB
    user = db.query(User).filter(User.email == "hacker@example.com").first()
    assert user is not None
    assert user.role == "sales_rep"


def test_production_rejects_weak_secret_and_wildcard_cors():
    """Vulnerability SEC-03 & SEC-12: Production must reject weak or default JWT secrets and wildcard CORS."""
    # Weak secret
    weak_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="short",
        BACKEND_CORS_ORIGINS=["http://localhost:5173"]
    )
    with pytest.raises(ValueError, match="Production SECRET_KEY must be a unique key"):
        weak_settings.validate_production_security()

    # Wildcard CORS
    wildcard_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a_very_long_production_secret_key_32_chars_minimum",
        BACKEND_CORS_ORIGINS=["*"]
    )
    with pytest.raises(ValueError, match="Wildcard CORS is strictly forbidden in production"):
        wildcard_settings.validate_production_security()


def test_refresh_token_rotation_and_revocation(client: TestClient, db: Session, test_sales_user: User):
    """Vulnerability SEC-04 & SEC-05: Refresh tokens rotate upon use and revoke old tokens."""
    # Login to receive access and refresh token
    login_resp = client.post("/api/v1/auth/login", data={
        "username": "sales@acttrident.ai",
        "password": "SalesPassword2026!"
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    first_refresh = data["refresh_token"]

    # Use refresh token to obtain rotated pair
    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert refresh_resp.status_code == 200
    rotated_data = refresh_resp.json()
    second_refresh = rotated_data["refresh_token"]
    assert second_refresh != first_refresh, "Refresh token must rotate upon consumption"

    # Attempting to replay the consumed refresh token must fail
    replay_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert replay_resp.status_code == 401, "Replaying a revoked or consumed refresh token must be rejected"


def test_role_restricted_approval_endpoint(client: TestClient, auth_headers: dict, admin_auth_headers: dict, db: Session, test_company: Company):
    """Vulnerability SEC-06: Approval endpoints must require admin or manager privileges."""
    draft = EmailDraft(
        company_id=test_company.id,
        recipient_email="test@company.com",
        subject="ActTrident Workspace Protection",
        body_text="Plain text body",
        body_html="<p>Html body</p>",
        approval_status="draft"
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    # Standard sales_rep attempt must be rejected (403 Forbidden)
    rep_resp = client.post(f"/api/v1/approvals/approve/{draft.id}", headers=auth_headers)
    assert rep_resp.status_code == 403, "Sales rep must not be permitted to approve drafts"

    # Admin attempt succeeds
    admin_resp = client.post(f"/api/v1/approvals/approve/{draft.id}", headers=admin_auth_headers)
    assert admin_resp.status_code == 200
    assert admin_resp.json()["approval_status"] == "approved"


def test_editing_approved_draft_invalidates_approval_and_increments_version(
    client: TestClient, admin_auth_headers: dict, db: Session, test_company: Company
):
    """Vulnerability SEC-07 & SEC-08: Editing an approved draft must invalidate approval and increment version."""
    draft = EmailDraft(
        company_id=test_company.id,
        recipient_email="executive@company.com",
        subject="Initial Approved Subject",
        body_text="Initial Body Text",
        body_html="<p>Initial Body</p>",
        approval_status="approved",
        approved_content_hash=compute_content_hash(["Initial Approved Subject", "Initial Body Text"]),
        version=1
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    # Edit subject of approved draft
    edit_resp = client.put(f"/api/v1/emails/drafts/{draft.id}", headers=admin_auth_headers, json={
        "subject": "Modified Subject After Approval"
    })
    assert edit_resp.status_code == 200
    updated_data = edit_resp.json()

    # Verify approval was invalidated
    assert updated_data["approval_status"] == "draft", "Editing an approved draft must reset status to draft"
    
    db.refresh(draft)
    assert draft.version == 2
    assert draft.approved_content_hash is None
    assert draft.approved_by_id is None


def test_content_tampering_blocks_dispatch(client: TestClient, admin_auth_headers: dict, db: Session, test_company: Company):
    """Vulnerability SEC-08: Dispatching an email with altered content hash must fail immediately."""
    original_hash = compute_content_hash(["Legitimate Subject", "Legitimate Body"])
    draft = EmailDraft(
        company_id=test_company.id,
        recipient_email="target@company.com",
        subject="Legitimate Subject",
        body_text="Tampered text injected directly in DB",
        body_html="<p>Tampered</p>",
        approval_status="approved",
        approved_content_hash=original_hash,
        version=1
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    # Send attempt must fail due to hash mismatch
    send_resp = client.post(f"/api/v1/emails/send/{draft.id}", headers=admin_auth_headers)
    assert send_resp.status_code == 400
    assert "content was modified" in send_resp.json()["detail"].lower()


def test_meta_webhook_hmac_signature_verification_and_idempotency(client: TestClient, db: Session):
    """Vulnerability SEC-10 & SEC-11: Webhooks must verify HMAC signature and deduplicate events."""
    secret = "test_meta_webhook_secret_key_123"
    settings.META_APP_SECRET = secret

    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "10001",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "919999999999"},
                    "statuses": [{"id": "wamid.TEST1", "status": "delivered"}]
                },
                "field": "messages"
            }]
        }]
    }
    raw_bytes = json.dumps(payload).encode('utf-8')

    # 1. Forged / invalid signature attempt must be rejected (403)
    bad_resp = client.post(
        "/api/v1/whatsapp/webhook",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=invalidhash"}
    )
    assert bad_resp.status_code == 403

    # 2. Legitimate HMAC-SHA256 signature
    mac = hmac.new(secret.encode('utf-8'), msg=raw_bytes, digestmod=hashlib.sha256)
    valid_signature = f"sha256={mac.hexdigest()}"

    good_resp = client.post(
        "/api/v1/whatsapp/webhook",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": valid_signature}
    )
    assert good_resp.status_code == 200

    # 3. Duplicate event with identical payload is acknowledged idempotently without duplication
    dup_resp = client.post(
        "/api/v1/whatsapp/webhook",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": valid_signature}
    )
    assert dup_resp.status_code == 200
    assert "duplicate" in dup_resp.json()["detail"].lower()


def test_simulated_dispatch_does_not_emit_real_delivered_event(
    client: TestClient, admin_auth_headers: dict, db: Session, test_company: Company
):
    """Vulnerability SEC-15: Mock provider dispatches must be recorded as simulated, never as delivered."""
    settings.EMAIL_PROVIDER = "mock"

    hash_val = compute_content_hash(["Subject Line", "Body Text"])
    draft = EmailDraft(
        company_id=test_company.id,
        recipient_email="mocktest@company.com",
        subject="Subject Line",
        body_text="Body Text",
        body_html="<p>Body</p>",
        approval_status="approved",
        approved_content_hash=hash_val,
        version=1
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    send_resp = client.post(f"/api/v1/emails/send/{draft.id}", headers=admin_auth_headers)
    assert send_resp.status_code == 200
    data = send_resp.json()
    assert data["status"] == "simulated", "Mock provider must return status 'simulated'"

    # Verify no fake 'delivered' event exists
    delivered_events = db.query(EmailEvent).filter(
        EmailEvent.draft_id == draft.id,
        EmailEvent.event_type == "delivered"
    ).all()
    assert len(delivered_events) == 0, "Simulated messages must never log real 'delivered' events"


def test_demo_record_separation(client: TestClient, auth_headers: dict, db: Session):
    """Vulnerability SEC-14: Demo records must have is_demo flag and be filterable."""
    c_demo = Company(name="Demo IT Corp", city="Siliguri", is_demo=True)
    c_real = Company(name="Real Client Corp", city="Siliguri", is_demo=False)
    db.add_all([c_demo, c_real])
    db.commit()

    # Query without demo records
    resp = client.get("/api/v1/companies?is_demo=false", headers=auth_headers)
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()["items"]]
    assert "Real Client Corp" in names
    assert "Demo IT Corp" not in names
