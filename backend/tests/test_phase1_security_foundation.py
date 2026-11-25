import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.crypto import encrypt_secret, decrypt_secret, mask_secret
from app.core.logging_config import redact_sensitive_text
from app.models.activity import IntegrationCredential
from app.models.company import Company
from app.models.email import EmailDraft, ApprovalRecord
from app.models.user import User
from app.services.auth_service import seed_default_admin
from app.services.email_sender_service import send_approved_email


def test_password_policy_rejects_weak_passwords(client: TestClient):
    """Weak passwords must be rejected on public registration with structured 422 response."""
    weak_passwords = ["short", "alllowercase123", "ALLUPPERCASE123", "NoDigitsHere!"]
    for pwd in weak_passwords:
        res = client.post(
            "/api/v1/auth/register",
            json={"email": "weak@acttrident.ai", "full_name": "Weak User", "password": pwd}
        )
        assert res.status_code == 422, f"Expected 422 for weak password '{pwd}'"
        body = res.json()
        assert body["error"] == "validation_error"
        assert "request_id" in body


def test_logout_immediately_revokes_access_and_refresh_tokens(client: TestClient, test_sales_user: User):
    """Logging out must increment token_version and immediately invalidate the current JWT access token."""
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "sales@acttrident.ai", "password": "SalesPassword2026!"}
    )
    assert login.status_code == 200
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]
    headers = {"Authorization": f"Bearer {access}"}

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    # Logout
    logout_res = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # Previously valid access token must immediately fail
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    # Previously valid refresh token must also fail
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401


def test_deactivating_user_immediately_blocks_active_jwt(
    client: TestClient, admin_auth_headers: dict, test_sales_user: User
):
    """Deactivating a user account must immediately block all active tokens and new logins."""
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "sales@acttrident.ai", "password": "SalesPassword2026!"}
    )
    sales_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=sales_headers).status_code == 200

    # Admin deactivates sales user
    deact = client.patch(
        f"/api/v1/auth/users/{test_sales_user.id}/status",
        json={"is_active": False},
        headers=admin_auth_headers
    )
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    # Existing active JWT is immediately rejected
    assert client.get("/api/v1/auth/me", headers=sales_headers).status_code == 403
    # New login is also blocked
    relogin = client.post(
        "/api/v1/auth/login",
        data={"username": "sales@acttrident.ai", "password": "SalesPassword2026!"}
    )
    assert relogin.status_code == 403


def test_role_change_invalidates_stale_jwt_claims(
    client: TestClient, admin_auth_headers: dict, test_sales_user: User
):
    """Updating a user's role rotates token_version so stale JWT claims are rejected."""
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "sales@acttrident.ai", "password": "SalesPassword2026!"}
    )
    old_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Admin promotes sales user to manager
    upd = client.patch(
        f"/api/v1/auth/users/{test_sales_user.id}/role",
        json={"role": "manager"},
        headers=admin_auth_headers
    )
    assert upd.status_code == 200
    assert upd.json()["role"] == "manager"

    # Old JWT with stale claims is rejected immediately
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401


def test_editing_draft_never_implicitly_approves_even_for_admin(
    client: TestClient, admin_auth_headers: dict, db: Session, test_company: Company
):
    """Editing a draft via PUT /emails/drafts/{id} must NEVER implicitly approve it, even for an admin."""
    gen = client.post(
        "/api/v1/emails/generate",
        json={"company_id": test_company.id, "tone": "Formal"},
        headers=admin_auth_headers
    )
    assert gen.status_code == 201
    draft_id = gen.json()["id"]

    # Attempt to implicitly approve while editing
    edit = client.put(
        f"/api/v1/emails/drafts/{draft_id}",
        json={
            "subject": "Updated Subject Line",
            "body_text": "Updated email body text",
            "approval_status": "approved"
        },
        headers=admin_auth_headers
    )
    assert edit.status_code == 200
    assert edit.json()["approval_status"] == "draft"

    # Also test trying to flip approval_status='approved' without content changes via PUT
    edit_only_status = client.put(
        f"/api/v1/emails/drafts/{draft_id}",
        json={"approval_status": "approved"},
        headers=admin_auth_headers
    )
    assert edit_only_status.status_code == 200
    assert edit_only_status.json()["approval_status"] == "draft"


def test_approval_ledger_records_approve_invalidation_and_reject(
    client: TestClient, admin_auth_headers: dict, db: Session, test_company: Company
):
    """Every approval, post-edit invalidation, and rejection creates an immutable ApprovalRecord."""
    draft_id = client.post(
        "/api/v1/emails/generate",
        json={"company_id": test_company.id, "tone": "Technical"},
        headers=admin_auth_headers
    ).json()["id"]

    # 1. Explicit approve
    assert client.post(f"/api/v1/approvals/approve/{draft_id}", headers=admin_auth_headers).status_code == 200
    # 2. Edit invalidates approval
    assert client.put(
        f"/api/v1/emails/drafts/{draft_id}",
        json={"subject": "Tampered Subject"},
        headers=admin_auth_headers
    ).status_code == 200
    # 3. Reject
    assert client.post(
        f"/api/v1/approvals/reject/{draft_id}",
        json={"reason": "Needs revision"},
        headers=admin_auth_headers
    ).status_code == 200

    records = (
        db.query(ApprovalRecord)
        .filter(ApprovalRecord.entity_type == "email_draft", ApprovalRecord.entity_id == draft_id)
        .order_by(ApprovalRecord.id.asc())
        .all()
    )
    actions = [r.action for r in records]
    assert actions == ["approved", "invalidated_by_edit", "rejected"]
    assert all(len(r.content_hash) == 64 for r in records)


def test_atomic_dispatch_lock_prevents_race_condition_double_send(
    client: TestClient, admin_auth_headers: dict, db: Session, test_company: Company
):
    """Atomic approved->sending transition prevents duplicate sends if dispatched twice."""
    draft_id = client.post(
        "/api/v1/emails/generate",
        json={"company_id": test_company.id, "tone": "Friendly professional"},
        headers=admin_auth_headers
    ).json()["id"]

    assert client.post(f"/api/v1/approvals/approve/{draft_id}", headers=admin_auth_headers).status_code == 200

    # First dispatch succeeds (simulated in mock mode)
    first = client.post(f"/api/v1/emails/send/{draft_id}", headers=admin_auth_headers)
    assert first.status_code == 200
    assert first.json()["status"] == "simulated"

    # Second dispatch of the same draft must be blocked
    second = client.post(f"/api/v1/emails/send/{draft_id}", headers=admin_auth_headers)
    assert second.status_code == 400


def test_integration_credentials_encrypted_at_rest_and_never_leaked(
    client: TestClient, admin_auth_headers: dict, db: Session
):
    """Saved API keys must be Fernet-encrypted in DB and masked in API responses."""
    raw_secret = "AIzaSySuperSecretLiveApiKey987654321"
    save = client.post(
        "/api/v1/settings/integrations",
        json={
            "provider": "gemini",
            "key_identifier": "GEMINI_API_KEY",
            "encrypted_value": raw_secret,
            "is_active": False
        },
        headers=admin_auth_headers
    )
    assert save.status_code == 200
    resp_data = save.json()
    assert raw_secret not in str(resp_data)
    assert resp_data["has_secret"] is True
    assert resp_data["masked_value"].endswith("4321")

    # Verify encrypted at rest in database
    row = db.query(IntegrationCredential).filter(IntegrationCredential.provider == "gemini").first()
    assert row is not None
    assert row.encrypted_value.startswith("enc:v1:")
    assert raw_secret not in row.encrypted_value
    assert decrypt_secret(row.encrypted_value) == raw_secret


def test_production_startup_guards_and_no_auto_admin_seeding(db: Session, monkeypatch):
    """Production rejects SQLite and missing CREDENTIAL_ENCRYPTION_KEY, and skips automatic admin seeding."""
    # Missing CREDENTIAL_ENCRYPTION_KEY in production
    no_enc = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a_very_long_production_secret_key_32_chars_minimum",
        BACKEND_CORS_ORIGINS=["https://app.acttrident.ai"],
        CREDENTIAL_ENCRYPTION_KEY="",
        DATABASE_URL="postgresql://user:pass@localhost/acttrident"
    )
    with pytest.raises(ValueError, match="CREDENTIAL_ENCRYPTION_KEY"):
        no_enc.validate_production_security()

    # SQLite forbidden in production
    sqlite_prod = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a_very_long_production_secret_key_32_chars_minimum",
        BACKEND_CORS_ORIGINS=["https://app.acttrident.ai"],
        CREDENTIAL_ENCRYPTION_KEY="super_secure_fernet_passphrase_2026",
        DATABASE_URL="sqlite:///./acttrident.db"
    )
    with pytest.raises(ValueError, match="SQLite is forbidden in production"):
        sqlite_prod.validate_production_security()

    # Automatic admin seeding must be skipped in production
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "INITIAL_ADMIN_EMAIL", "prod_auto@acttrident.ai")
    monkeypatch.setattr(settings, "INITIAL_ADMIN_PASSWORD", "AutoSeedPass123!")
    assert seed_default_admin(db) is None


def test_health_readiness_correlation_id_and_secret_redaction(client: TestClient):
    """Verify /health, /ready, X-Request-ID propagation, and log secret redaction."""
    h = client.get("/health", headers={"X-Request-ID": "corr-test-001"})
    assert h.status_code == 200
    assert h.headers.get("X-Request-ID") == "corr-test-001"

    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    assert r.json()["database"] == "connected"
    assert "X-Request-ID" in r.headers

    # Secret redaction helper check
    raw_log = 'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.secret.sig {"password": "MySecretPassword123"}'
    redacted = redact_sensitive_text(raw_log)
    assert "eyJhbGciOiJIUzI1NiJ9" not in redacted
    assert "MySecretPassword123" not in redacted
    assert "[REDACTED]" in redacted


def test_sales_rep_cannot_dispatch_email_or_modify_other_campaign(
    client: TestClient, auth_headers: dict, admin_auth_headers: dict, test_company: Company
):
    """Unauthorized sales_rep cannot dispatch emails or add recipients to another user's campaign."""
    draft_id = client.post(
        "/api/v1/emails/generate",
        json={"company_id": test_company.id, "tone": "Formal"},
        headers=auth_headers
    ).json()["id"]
    client.post(f"/api/v1/approvals/approve/{draft_id}", headers=admin_auth_headers)

    # Sales rep cannot dispatch even an approved email
    rep_send = client.post(f"/api/v1/emails/send/{draft_id}", headers=auth_headers)
    assert rep_send.status_code == 403

    # Admin creates a campaign; sales_rep cannot modify its recipients
    camp_res = client.post(
        "/api/v1/campaigns",
        json={"name": "Admin Executive Campaign", "objective": "90-day evaluation outreach", "target_city": "Siliguri"},
        headers=admin_auth_headers
    )
    assert camp_res.status_code == 201
    camp = camp_res.json()
    rep_add = client.post(
        f"/api/v1/campaigns/{camp['id']}/recipients",
        json={"company_ids": [test_company.id]},
        headers=auth_headers
    )
    assert rep_add.status_code == 403
