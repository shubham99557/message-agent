"""
Production Hardening Verification Test Suite
Validates the final hardening requirements:
1. Mandatory Individual Human Approval Enforcement (bulk approve forbidden)
2. Product Claims Registry and Evaluation Offer Guard
3. Inbound Reply Classification Hardening (bounce detection, unknown fail-closed)
4. WhatsApp Template Verification State and Click-to-Chat Fallback
5. Durable Automation Scheduler Persistence in SQLite
6. 7-Factor Qualification Deterministic Evidence Scoring & Verification States
"""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.product_claims import (
    get_approved_claims_summary,
    validate_message_against_claims,
    APPROVED_EVALUATION_OFFER,
)
from app.models.company import Company
from app.models.lead import Lead
from app.models.email import EmailDraft
from app.models.whatsapp import WhatsAppTemplate, WhatsAppMessage
from app.models.orchestration import SchedulerJobRecord, SchedulerExecutionHistory
from app.schemas.email import BulkApprovalRequest
from app.services.approval_service import bulk_handle_approvals
from app.services.reply_classifier_service import classify_reply_text, ingest_inbound_reply
from app.services.whatsapp_service import (
    DEFAULT_TEMPLATES,
    seed_default_meta_templates,
    create_whatsapp_message,
)
from app.schemas.whatsapp import WhatsAppDraftRequest
from app.services.local_scheduler import LocalScheduler
from app.services.qualification_service import qualify_company
from app.integrations.whatsapp_adapter import validate_and_order_template_parameters, MetaWhatsAppError


def test_mandatory_human_approval_disallows_bulk_outbound_approval(client: TestClient, db: Session, monkeypatch):
    """Bulk approval for outbound messages is strictly prohibited at both API and service layers."""
    # Test service layer raises ValueError
    req = BulkApprovalRequest(draft_ids=[1, 2, 3], action="approve")
    with pytest.raises(ValueError, match="Bulk outbound approval is strictly prohibited"):
        bulk_handle_approvals(db, req, user_id=1)

    # Test API endpoint returns 400
    # First login as manager/admin
    login_resp = client.post("/api/v1/auth/login", data={"username": "admin@acttrident.com", "password": "AdminPassword123!"})
    if login_resp.status_code == 200:
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post("/api/v1/approvals/bulk", json={"draft_ids": [1, 2], "action": "approve"}, headers=headers)
        assert resp.status_code == 400
        assert "strictly prohibited" in resp.json()["detail"].lower()


def test_product_claims_registry_guarded_by_setting(monkeypatch):
    """90-day evaluation offer is properly guarded by configuration and disallowed claims are caught."""
    # When enabled
    monkeypatch.setattr(settings, "ALLOW_90_DAY_EVALUATION_OFFER", True)
    summary_enabled = get_approved_claims_summary()
    assert "90-Day Free Product Evaluation" in summary_enabled

    # When disabled
    monkeypatch.setattr(settings, "ALLOW_90_DAY_EVALUATION_OFFER", False)
    summary_disabled = get_approved_claims_summary()
    assert "90-Day Free Product Evaluation" not in summary_disabled

    # Prohibited claims detection
    valid, violations = validate_message_against_claims("Our tool is 100% hack-proof and uses military grade encryption.")
    assert valid is False
    assert len(violations) >= 2


def test_reply_classification_bounce_and_unknown_handling(db: Session):
    """Bounce messages are accurately classified as bounce, and ambiguous text fails closed to unknown."""
    # Bounce detection
    bounce_text = "Mail Delivery Subsystem <mailer-daemon@googlemail.com>: Delivery status notification: 550 5.1.1 User unknown"
    cat, conf, reason, suggested, is_neg = classify_reply_text(bounce_text)
    assert cat == "bounce"
    assert conf >= 0.95
    assert is_neg is False

    # Ambiguous unrecognized text
    ambiguous_text = "xyz 123 lorem ipsum dolor sit amet qwerty"
    cat, conf, reason, suggested, is_neg = classify_reply_text(ambiguous_text)
    assert cat == "unknown"
    assert conf == 0.0

    # Explicit inquiry maps to wants_more_information
    inquiry_text = "Can you send more details and an overview brochure of what ActTrident does?"
    cat, conf, reason, suggested, is_neg = classify_reply_text(inquiry_text)
    assert cat == "wants_more_information"
    assert conf > 0.8


def test_reply_ingestion_bounce_sets_suppression_and_lead_status(db: Session):
    """Inbound bounce automatically suppresses recipient identifier and marks lead bounced."""
    comp = Company(
        name="Test Bounce Target",
        city="Patna",
        public_email="bounce_test@patnafirm.in",
        public_phone="+919832099999",
        qualification_status="Needs manual verification",
    )
    db.add(comp)
    db.flush()
    lead = Lead(company_id=comp.id, pipeline_status="contacted")
    db.add(lead)
    db.commit()

    bounce_payload = "Delivery Failure: 550 Mailbox unavailable for bounce_test@patnafirm.in"
    reply = ingest_inbound_reply(
        db=db,
        channel="email",
        sender_identifier="bounce_test@patnafirm.in",
        recipient_identifier="outreach@acttrident.com",
        subject="Undelivered Mail Returned to Sender",
        message_body=bounce_payload,
    )
    assert reply.classification == "bounce"

    db.refresh(lead)
    assert lead.pipeline_status == "bounced"


def test_whatsapp_templates_default_status_and_click_to_chat(db: Session):
    """Locally seeded templates default to PENDING_META_VERIFICATION and unverified templates generate click-to-chat fallback."""
    seed_default_meta_templates(db)
    for t in DEFAULT_TEMPLATES:
        assert t["status"] == "PENDING_META_VERIFICATION"

    comp = Company(
        name="Test WhatsApp Target",
        city="Siliguri",
        public_phone="+919832088888",
        public_whatsapp="+919832088888",
        qualification_status="Qualified",
    )
    db.add(comp)
    db.commit()

    draft_req = WhatsAppDraftRequest(
        company_id=comp.id,
        recipient_phone="+919832088888",
        template_name="acttrident_intro_utility_v1",
        parameters={"1": "Amitabh", "2": "Siliguri"},
    )
    msg = create_whatsapp_message(db, comp, draft_req)
    assert msg.id is not None
    # Click-to-chat fallback is generated
    assert msg.click_to_chat_url is not None
    assert "https://wa.me/919832088888" in msg.click_to_chat_url

    # Automated send with require_meta_approved=True raises MetaWhatsAppError
    with pytest.raises(MetaWhatsAppError, match="not approved by Meta"):
        validate_and_order_template_parameters(msg.template, {"1": "Amitabh", "2": "Siliguri"}, require_meta_approved=True)


def test_scheduler_persists_state_in_sqlite(db: Session):
    """LocalScheduler persists job runs, execution records, and recovers state across restarts."""
    scheduler = LocalScheduler()
    # Trigger database_backup
    res = scheduler.trigger_job("database_backup", db=db)
    assert res.get("status") in ("executed", "success", True) or "backup_file" in res

    # Verify SchedulerJobRecord in database
    rec = db.query(SchedulerJobRecord).filter(SchedulerJobRecord.job_name == "database_backup").first()
    assert rec is not None
    assert rec.total_runs >= 1
    assert rec.last_run_at is not None

    # Verify SchedulerExecutionHistory
    hist = db.query(SchedulerExecutionHistory).filter(SchedulerExecutionHistory.job_name == "database_backup").first()
    assert hist is not None

    # Create a fresh scheduler and ensure it recovers last_run from SQLite
    fresh_scheduler = LocalScheduler()
    assert fresh_scheduler.last_run["database_backup"] is None
    fresh_scheduler.load_persisted_state(db=db)
    assert fresh_scheduler.last_run["database_backup"] is not None


def test_qualification_deterministic_scoring_and_verification_states(db: Session):
    """Seven-factor qualification assigns 0 points for unknown evidence and tracks explicit verification states."""
    # Company with empty / unknown data
    empty_company = Company(
        name="Unknown Entity",
        city="Unknown",
        website="https://unknown-entity.in",
        description=None,
        laptop_count_verified=0,
        has_verified_5_plus_laptops=False,
        laptop_fleet_status="UNKNOWN",
    )
    db.add(empty_company)
    db.commit()

    result = qualify_company(db, empty_company)
    assert result.score == 0.0
    assert result.status == "Not suitable"
    assert len(result.factors) == 7

    for f in result.factors:
        assert f.verification_state in ("UNKNOWN", "CLAIMED", "VERIFIED")
        assert f.score_weight == 0.0
