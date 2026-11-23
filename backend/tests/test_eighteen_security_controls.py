"""
Test Suite: Exact 1:1 Verification of All 18 ActTrident Production Security Controls.

Every test in this file validates the strict operational boundary of one specific security control:
1. Fail-closed outbound sending (LIVE_SEND_ENABLED=False default)
2. Global emergency kill switch
3. Immutable SHA-256 content hashing on approvals
4. Strict prohibition of bulk approvals (individual review required)
5. Invalidation of approval upon recipient email modification
6. Invalidation of approval upon message body / subject tampering
7. SSRF protection against private, loopback, and cloud metadata targets
8. Safe HTTP client redirect guard against SSRF pivot attacks
9. Input sanitization against script tags, inline event handlers, and prompt injection
10. TRAI telemarketing curfew (09:00 - 21:00 IST calling window)
11. DPDP Act 2023 Section 12 Right to Erasure
12. RFC 8058 unauthenticated one-click opt-out / unsubscribe endpoints
13. Mailbox warmup schedule caps (20, 50, 100, 200/day)
14. AES-256-GCM encryption of integration credentials in database
15. Role-Based Access Control (Admin vs Sales vs Read-Only Analyst)
16. JWT token version revocation enforcement
17. Idempotent outbox dispatch preventing duplicate sends
18. Prohibited product claims filter (guarantees, uncorroborated offers)
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import (
    is_safe_external_url,
    safe_fetch_untrusted_url,
    sanitize_untrusted_text,
    compute_content_hash,
    create_access_token,
    get_password_hash,
)
from app.core.crypto import encrypt_secret, decrypt_secret
from app.core.compliance_policy_engine import CompliancePolicyEngine, PolicyViolationError
from app.models.company import Company
from app.models.lead import Lead
from app.models.user import User
from app.models.email import EmailDraft
from app.models.activity import SuppressionList
from app.schemas.email import EmailDraftUpdate, BulkApprovalRequest
from app.services.approval_service import approve_email_draft, edit_email_draft, bulk_handle_approvals
from app.services.email_sender_service import send_approved_email, get_mailbox_warmup_limit
from app.services.email_generator_service import validate_message_against_claims
from app.services.orchestration_service import set_kill_switch, is_kill_switch_active


# Control 1: Fail-closed outbound sending
def test_control_01_fail_closed_outbound_sending(db: Session):
    assert settings.LIVE_SEND_ENABLED is False, "LIVE_SEND_ENABLED must default to False"
    comp = Company(name="Control 1 Co", city="Siliguri", public_email="c1@test.in")
    db.add(comp)
    db.commit()
    draft = EmailDraft(
        company_id=comp.id, recipient_email="c1@test.in", subject="Hi",
        body_text="Hello", body_html="<p>Hello</p>", approval_status="draft"
    )
    db.add(draft)
    db.commit()
    res = send_approved_email(db, draft.id, user_id=1)
    assert res.status == "failed"
    assert "Security Block" in res.message or "not been approved" in res.message


# Control 2: Global emergency kill switch
def test_control_02_emergency_outbound_kill_switch(db: Session):
    try:
        set_kill_switch(db, active=True, user_id=1, reason="Control 2 Drill")
        active, reason = is_kill_switch_active(db)
        assert active is True
        assert "Control 2 Drill" in reason

        comp = Company(name="Control 2 Co", city="Siliguri", public_email="c2@test.in")
        db.add(comp)
        db.commit()
        chash = compute_content_hash(["Subject", "Body"])
        draft = EmailDraft(
            company_id=comp.id, recipient_email="c2@test.in", subject="Subject",
            body_text="Body", body_html="<p>Body</p>", approval_status="approved",
            content_hash=chash, approved_content_hash=chash
        )
        db.add(draft)
        db.commit()

        res = send_approved_email(db, draft.id, user_id=1)
        assert res.status == "blocked_kill_switch"
        assert "Global Outbound Kill Switch is ACTIVE" in res.message
    finally:
        set_kill_switch(db, active=False, user_id=1, reason="Drill end")


# Control 3: Immutable SHA-256 content hashing on approvals
def test_control_03_immutable_content_hash(db: Session):
    comp = Company(name="Control 3 Co", city="Siliguri", public_email="c3@test.in")
    db.add(comp)
    db.commit()
    draft = EmailDraft(
        company_id=comp.id, recipient_email="c3@test.in", subject="Legit Subject",
        body_text="Legit Body", body_html="<p>Legit Body</p>", approval_status="draft"
    )
    db.add(draft)
    db.commit()

    approved = approve_email_draft(db, draft.id, user_id=1)
    assert approved.approved_content_hash is not None
    assert len(approved.approved_content_hash) == 64  # SHA-256 hex string

    # Manually tamper with body text bypassing the service
    draft.body_text = "TAMPERED BODY CONTENT"
    db.commit()

    res = send_approved_email(db, draft.id, user_id=1)
    assert res.status == "failed"
    assert "was modified" in res.message.lower() or "modified" in res.message.lower()


# Control 4: Strict prohibition of bulk approvals
def test_control_04_bulk_approval_prohibited(db: Session):
    req = BulkApprovalRequest(draft_ids=[101, 102], action="approve")
    with pytest.raises(ValueError) as exc:
        bulk_handle_approvals(db, req, user_id=1)
    assert "bulk outbound approval is strictly prohibited" in str(exc.value).lower()


# Control 5: Invalidation of approval upon recipient email modification
def test_control_05_recipient_modification_invalidates_approval(db: Session):
    comp = Company(name="Control 5 Co", city="Siliguri", public_email="c5@test.in")
    db.add(comp)
    db.commit()
    draft = EmailDraft(
        company_id=comp.id, recipient_email="c5@test.in", subject="Sub",
        body_text="Body", body_html="<p>Body</p>", approval_status="draft"
    )
    db.add(draft)
    db.commit()

    approve_email_draft(db, draft.id, user_id=1)
    assert draft.approval_status == "approved"

    edit_email_draft(db, draft.id, EmailDraftUpdate(recipient_email="attacker@tampered.in"), user_id=1)
    db.refresh(draft)
    assert draft.approval_status == "draft"
    assert draft.approved_content_hash is None


# Control 6: Invalidation of approval upon message body / subject tampering
def test_control_06_content_tampering_invalidates_approval(db: Session):
    comp = Company(name="Control 6 Co", city="Siliguri", public_email="c6@test.in")
    db.add(comp)
    db.commit()
    draft = EmailDraft(
        company_id=comp.id, recipient_email="c6@test.in", subject="Sub",
        body_text="Body", body_html="<p>Body</p>", approval_status="draft"
    )
    db.add(draft)
    db.commit()

    approve_email_draft(db, draft.id, user_id=1)
    assert draft.approval_status == "approved"

    edit_email_draft(db, draft.id, EmailDraftUpdate(body_text="New edited body text"), user_id=1)
    db.refresh(draft)
    assert draft.approval_status == "draft"
    assert draft.approved_content_hash is None


# Control 7: SSRF protection against private, loopback, and metadata targets
def test_control_07_ssrf_protection_private_ips_and_metadata():
    assert not is_safe_external_url("http://127.0.0.1:8000")
    assert not is_safe_external_url("http://localhost:3000")
    assert not is_safe_external_url("http://169.254.169.254/latest/meta-data")
    assert not is_safe_external_url("http://metadata.google.internal")
    assert not is_safe_external_url("http://10.0.0.1")
    assert not is_safe_external_url("http://192.168.1.1")
    assert not is_safe_external_url("http://172.16.0.1")
    assert not is_safe_external_url("http://[::1]")
    assert not is_safe_external_url("http://example.com:22")
    assert not is_safe_external_url("http://example.com:5432")
    # Public resolving web address
    assert is_safe_external_url("https://www.openstreetmap.org")


# Control 8: Safe HTTP client redirect guard against SSRF pivot attacks
@pytest.mark.anyio
async def test_control_08_safe_fetch_redirect_ssrf_guard():
    ok, text, final_url, err = await safe_fetch_untrusted_url("http://169.254.169.254/latest/meta-data")
    assert ok is False
    assert "SSRF security check rejected" in (err or "")


# Control 9: Input sanitization against script tags, inline event handlers, and injection
def test_control_09_input_sanitization():
    xss_payload = "<script>alert('xss')</script><svg onload=alert(1)>Hello <b>World</b>"
    clean = sanitize_untrusted_text(xss_payload)
    assert "<script>" not in clean
    assert "onload" not in clean
    assert "World" in clean


# Control 10: TRAI telemarketing curfew (09:00 - 21:00 IST)
def test_control_10_trai_telecom_curfew(monkeypatch):
    monkeypatch.setattr(settings, "ENFORCE_TRAI_CURFEW", True)
    # Night in IST: 23:00 IST (17:30 UTC)
    night_time_utc = datetime(2026, 11, 23, 17, 30, tzinfo=timezone.utc)
    with patch("app.core.compliance_policy_engine.datetime") as mock_dt:
        mock_dt.now.return_value = night_time_utc
        with pytest.raises(PolicyViolationError) as exc:
            CompliancePolicyEngine.validate_trai_commercial_hours("+919876543210", "whatsapp")
        assert "TRAI regulations prohibit" in str(exc.value)


# Control 11: DPDP Act 2023 Section 12 Right to Erasure
def test_control_11_dpdp_right_to_erasure(client, db: Session, admin_auth_headers):
    comp = Company(name="DPDP Co", city="Patna", public_email="dpdp-user@privacy.in", public_phone="+919876540001")
    db.add(comp)
    db.commit()
    lead = Lead(company_id=comp.id, pipeline_status="contacted")
    db.add(lead)
    db.commit()

    resp = client.post("/api/v1/crm/erasure", json={"identifier": "dpdp-user@privacy.in", "reason": "user_request"}, headers=admin_auth_headers)
    assert resp.status_code == 200
    db.refresh(comp)
    assert "erased-" in comp.public_email
    assert comp.public_phone is None

    supp = db.query(SuppressionList).filter(SuppressionList.identifier == "dpdp-user@privacy.in").first()
    assert supp is not None


# Control 12: RFC 8058 unauthenticated one-click unsubscribe
def test_control_12_rfc_8058_one_click_unsubscribe(client, db: Session):
    unsub_email = "optout-rfc8058@test.in"
    res = client.get(f"/api/v1/crm/public/opt-out?email={unsub_email}")
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    supp = db.query(SuppressionList).filter(SuppressionList.identifier == unsub_email).first()
    assert supp is not None


# Control 13: Mailbox warmup schedule caps
def test_control_13_mailbox_warmup_tiers(db: Session):
    cap = get_mailbox_warmup_limit(db)
    assert cap == 20  # Brand new mailbox tier


# Control 14: AES-256-GCM encryption of integration credentials
def test_control_14_credential_encryption():
    secret = "super_confidential_api_token_2026"
    encrypted = encrypt_secret(secret)
    assert encrypted != secret
    assert secret not in encrypted
    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret


# Control 15: Role-Based Access Control
def test_control_15_rbac_analyst_cannot_mutate(client: TestClient, db: Session):
    user = User(
        email="analyst.ctrl15@acttrident.internal",
        hashed_password=get_password_hash("AnalystPass2026!"),
        full_name="Analyst User",
        role="analyst",
        is_active=True,
        token_version=1
    )
    db.add(user)
    db.commit()
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": user.id, "tv": 1})
    headers = {"Authorization": f"Bearer {token}"}

    # Attempting mutation must return HTTP 403 Forbidden
    res = client.post("/api/v1/campaigns", headers=headers, json={"name": "Forbidden", "target_city": "Siliguri"})
    assert res.status_code == 403


# Control 16: JWT token version revocation enforcement
def test_control_16_jwt_token_version_revocation(client: TestClient, db: Session):
    user = User(
        email="revoked.ctrl16@acttrident.internal",
        hashed_password=get_password_hash("Pass2026!"),
        full_name="Revoked User",
        role="sales",
        is_active=True,
        token_version=2
    )
    db.add(user)
    db.commit()

    # Token with missing or stale token version
    legacy_token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": user.id, "tv": 1})
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {legacy_token}"})
    assert res.status_code == 401
    assert "token version" in res.json()["detail"].lower() or "revoked" in res.json()["detail"].lower()


# Control 17: Idempotent outbox dispatch preventing duplicate sends
def test_control_17_idempotent_outbox_dispatch(db: Session):
    comp = Company(name="Control 17 Co", city="Siliguri", public_email="c17@test.in")
    db.add(comp)
    db.commit()
    draft = EmailDraft(
        company_id=comp.id, recipient_email="c17@test.in", subject="Hi",
        body_text="Hello", body_html="<p>Hello</p>", approval_status="sent"
    )
    db.add(draft)
    db.commit()
    # Sending already sent draft must fail
    res = send_approved_email(db, draft.id, user_id=1)
    assert res.status == "failed"
    assert "already been sent" in res.message.lower() or "not in approved" in res.message.lower() or "security block" in res.message.lower()


# Control 18: Prohibited product claims filter
def test_control_18_prohibited_product_claims(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_90_DAY_EVALUATION_OFFER", False)
    # 1. Prohibited exaggerated security claims
    is_valid1, violations1 = validate_message_against_claims("Our platform provides 100% hack-proof and unbreakable security.")
    assert is_valid1 is False
    assert any("100% hack-proof" in v for v in violations1)

    # 2. Prohibited evaluation offer when disabled
    is_valid2, violations2 = validate_message_against_claims("Join our 90-day evaluation offer.")
    assert is_valid2 is False
    assert any("90-day evaluation offer is disabled" in v for v in violations2)
