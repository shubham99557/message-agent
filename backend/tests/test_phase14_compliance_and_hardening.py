import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.core.compliance_policy_engine import CompliancePolicyEngine, PolicyViolationError
from app.services.email_sender_service import get_mailbox_warmup_limit
from app.integrations.discovery_adapters import _throttle_nominatim
from app.services.discovery_service import (
    _get_discovery_cache_key,
    get_cached_discovery_results,
    set_cached_discovery_results
)
from app.schemas.research import DiscoveryQuery, DiscoveredCompanyItem
from app.models.activity import SuppressionList
from app.models.company import Company, CompanyContact
from app.models.lead import Lead
from app.api.endpoints.auth import _failed_login_attempts


def test_trai_commercial_hours_restriction():
    """Validates TRAI TCCCPR 2018 calling-window restriction (09:00 - 21:00 IST)."""
    # 1. Non-Indian number should pass regardless of hour
    CompliancePolicyEngine.validate_trai_commercial_hours("+14155552671", "whatsapp")

    # 2. Non-telecom channel (e.g. email) should pass
    CompliancePolicyEngine.validate_trai_commercial_hours("+919876543210", "email")

    # 3. Simulate night hour in IST (e.g. 23:00 IST / 17:30 UTC)
    night_time_utc = datetime(2026, 11, 19, 17, 30, tzinfo=timezone.utc)
    with patch("app.core.compliance_policy_engine.datetime") as mock_dt:
        mock_dt.now.return_value = night_time_utc
        with pytest.raises(PolicyViolationError) as exc_info:
            CompliancePolicyEngine.validate_trai_commercial_hours("+919876543210", "whatsapp")
        assert "TRAI regulations prohibit automated commercial telecommunications" in str(exc_info.value)

    # 4. Simulate working business hour in IST (e.g. 14:00 IST / 08:30 UTC)
    day_time_utc = datetime(2026, 11, 19, 8, 30, tzinfo=timezone.utc)
    with patch("app.core.compliance_policy_engine.datetime") as mock_dt:
        mock_dt.now.return_value = day_time_utc
        # Should execute cleanly without error
        CompliancePolicyEngine.validate_trai_commercial_hours("+919876543210", "whatsapp")


def test_mailbox_warmup_schedule_tiers(db: Session):
    """Verifies that daily sending caps adhere to the domain warm-up schedule."""
    # Brand new mailbox with zero sends defaults to tier 1 (20/day)
    tier1_cap = get_mailbox_warmup_limit(db)
    assert tier1_cap == 20


def test_discovery_redis_cache_key_generation():
    """Verifies deterministic cache key generation for discovery queries."""
    q1 = DiscoveryQuery(query="software", city="Siliguri", state="West Bengal", industry="IT", scope="city")
    q2 = DiscoveryQuery(query="software", city="siliguri", state="west bengal", industry="it", scope="city")
    assert _get_discovery_cache_key(q1) == _get_discovery_cache_key(q2)


def test_nominatim_rate_limiter_throttling():
    """Validates that rapid consecutive calls to _throttle_nominatim maintain spacing."""
    t0 = datetime.now(timezone.utc)
    _throttle_nominatim(min_interval=0.05)
    _throttle_nominatim(min_interval=0.05)
    t1 = datetime.now(timezone.utc)
    assert (t1 - t0).total_seconds() >= 0.04


def test_public_one_click_unsubscribe_endpoints(client, db: Session):
    """Verifies RFC 8058 public GET and POST unsubscribe endpoints without authentication."""
    # Public GET opt-out
    test_email_1 = "unsub-get-test@privacy.example.com"
    resp_get = client.get(f"/api/v1/crm/public/opt-out?email={test_email_1}")
    assert resp_get.status_code == 200
    assert resp_get.json()["status"] == "success"

    # Check suppression table
    suppressed = db.query(SuppressionList).filter(SuppressionList.identifier == test_email_1).first()
    assert suppressed is not None
    assert suppressed.channel == "all"

    # Public POST opt-out (RFC 8058 One-Click)
    test_email_2 = "unsub-post-test@privacy.example.com"
    resp_post = client.post("/api/v1/crm/public/opt-out", json={"identifier": test_email_2, "channel": "email"})
    assert resp_post.status_code == 200
    assert resp_post.json()["status"] == "success"

    suppressed_post = db.query(SuppressionList).filter(SuppressionList.identifier == test_email_2).first()
    assert suppressed_post is not None


def test_dpdp_right_to_erasure_execution(client, db: Session, admin_auth_headers):
    """Validates DPDP Act 2023 Section 12 Right to Erasure / Right to be Forgotten."""
    # Create dummy prospect company and contact
    comp = Company(
        name="Privacy Test Enterprises",
        public_email="privacy-erasure@company.example.com",
        public_phone="+91-9876500000",
        city="Patna",
        state="Bihar",
        industry="IT Services"
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)

    lead = Lead(company_id=comp.id, pipeline_status="contacted")
    db.add(lead)
    db.commit()

    # Request erasure via endpoint
    resp = client.post(
        "/api/v1/crm/erasure",
        json={"identifier": "privacy-erasure@company.example.com", "reason": "data_subject_request"},
        headers=admin_auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # Check that company PII was scrubbed
    db.refresh(comp)
    assert "erased-" in comp.public_email
    assert comp.public_phone is None
    assert comp.lead.pipeline_status == "do_not_contact"

    # Check that identifier is suppressed forever
    suppressed = db.query(SuppressionList).filter(SuppressionList.identifier == "privacy-erasure@company.example.com").first()
    assert suppressed is not None


def test_auth_route_rate_limiting_lockout(client):
    """Validates that 5 consecutive failed logins trigger HTTP 429 lockout."""
    _failed_login_attempts.clear()

    bad_creds = {"email": "attacker-test@target.example.com", "password": "WrongPassword123!"}

    # First 4 attempts should return 401 Unauthorized
    for _ in range(4):
        resp = client.post("/api/v1/auth/login/json", json=bad_creds)
        assert resp.status_code == 401

    # 5th attempt: should record failure and return 401
    resp = client.post("/api/v1/auth/login/json", json=bad_creds)
    assert resp.status_code == 401

    # 6th attempt: should be blocked by rate limiter with 429 Too Many Requests
    resp = client.post("/api/v1/auth/login/json", json=bad_creds)
    assert resp.status_code == 429
    assert "Too many failed login attempts" in resp.json()["detail"]

    # Clean up
    _failed_login_attempts.clear()
