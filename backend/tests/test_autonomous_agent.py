"""
Tests for ActTrident Autonomous Sales Outreach Agent & Brain Orchestrator.
Verifies the end-to-end autonomous lifecycle:
Discovery -> AI Research -> 7-Factor Qualification -> Campaign Enrollment
-> Multi-Channel Drafting -> Approval Safeguard -> Outbox Staging & Dispatch -> CRM Pipeline.
"""
import asyncio
import pytest
from app.services.autonomous_agent_service import (
    ensure_verified_targets,
    run_autonomous_outreach_cycle,
    get_autonomous_agent_status,
)
from app.services.orchestration_service import set_kill_switch
from app.models.company import Company
from app.models.campaign import Campaign
from app.models.email import EmailDraft
from app.models.whatsapp import WhatsAppMessage
from app.models.orchestration import OutboundDispatchOutbox
from app.worker.tasks import execute_task_logic


def test_ensure_verified_targets(db_session):
    """Verifies that regional enterprise targets are seeded with authentic 5+ laptop evidence and scored."""
    companies = ensure_verified_targets(db_session)
    assert len(companies) >= 7

    for c in companies:
        assert c.verification_status == "verified"
        assert c.has_verified_5_plus_laptops is True
        assert c.laptop_count_verified is not None
        assert c.laptop_count_verified >= 5
        assert c.laptop_count_evidence is not None
        assert c.qualification_score >= 80.0
        assert c.qualification_status == "High priority"
        assert c.city in ["Siliguri", "Gangtok", "Patna", "Bhagalpur"]


def test_ensure_verified_targets_custom_city(db_session):
    """Verifies that ensure_verified_targets supports ANY custom city given by admin."""
    # Pre-populate a custom city enterprise
    comp = Company(
        name="Bengaluru Cloud AI Corp",
        website="https://bengalurucloud.example.org",
        city="Bengaluru",
        state="Karnataka",
        country="India",
        industry="Software Development",
        laptop_count_verified=15,
        laptop_count_evidence="Careers portal verified 15 developer laptops",
        has_verified_5_plus_laptops=True,
        employee_count_min=20,
        employee_count_max=40,
        employee_size_evidence="MCA filings",
        decision_maker_name="Sunil Rao",
        decision_maker_role="VP Engineering",
        public_email="contact@bengalurucloud.example.org",
        public_phone="+91-80-45678900",
        verification_status="verified",
        verification_method="public_evidence_review",
        is_demo=False,
    )
    db_session.add(comp)
    db_session.commit()

    targets = ensure_verified_targets(db_session, target_city="Bengaluru")
    assert len(targets) >= 1
    found = next((t for t in targets if t.name == "Bengaluru Cloud AI Corp"), None)
    assert found is not None
    assert found.city == "Bengaluru"
    assert found.has_verified_5_plus_laptops is True
    assert found.qualification_score >= 80.0


def test_get_autonomous_agent_status(db_session):
    """Verifies agent telemetry and status reporting."""
    status = get_autonomous_agent_status(db_session)
    assert "agent_name" in status
    assert "version" in status
    assert status["kill_switch"]["active"] is False
    assert status["live_send_enabled"] is False  # Safe fail-closed default
    assert "Siliguri" in status["supported_clusters"]
    assert "email" in status["supported_channels"]


def test_run_autonomous_outreach_cycle_safe_simulation(db_session):
    """Verifies end-to-end execution of the 8-phase outreach pipeline in safe simulation mode."""
    res = asyncio.run(run_autonomous_outreach_cycle(
        db=db_session,
        target_city="Siliguri",
        channels=["email", "whatsapp"],
        max_prospects=2,
        auto_approve_simulation=True,
        user_id=1,
    ))

    assert res["status"] == "completed"
    metrics = res["metrics"]
    assert metrics["prospects_discovered"] >= 2
    assert metrics["researched"] >= 2
    assert metrics["qualified"] >= 2
    assert metrics["drafts_created"] >= 2
    assert metrics["approved"] >= 2
    assert metrics["outbox_queued"] >= 2
    assert metrics["dispatched"] >= 2

    # Verify execution logs contain all phases
    steps = [log["step"] for log in res["logs"]]
    assert "discovery" in steps
    assert "brain" in steps
    assert "qualification" in steps
    assert "copywriting" in steps
    assert "approval" in steps
    assert "dispatch" in steps
    assert "complete" in steps

    # Verify outbox items were marked as dispatched
    outbox_items = db_session.query(OutboundDispatchOutbox).filter(
        OutboundDispatchOutbox.channel == "email",
        OutboundDispatchOutbox.status == "dispatched"
    ).all()
    assert len(outbox_items) >= 2


def test_run_autonomous_cycle_kill_switch_halt(db_session):
    """Verifies that activating the Global Kill Switch immediately halts the autonomous agent cycle."""
    set_kill_switch(db_session, active=True, user_id=1, reason="Test emergency stop")

    res = asyncio.run(run_autonomous_outreach_cycle(
        db=db_session,
        target_city="Siliguri",
        auto_approve_simulation=True,
    ))

    assert res["status"] == "halted_by_kill_switch"
    assert "Test emergency stop" in res["reason"]
    assert res["metrics"]["drafts_created"] == 0
    assert res["metrics"]["dispatched"] == 0

    # Reset kill switch for following tests
    set_kill_switch(db_session, active=False, user_id=1, reason="Resume normal testing")


def test_agent_api_endpoints(client, admin_auth_headers):
    """Verifies FastAPI API endpoints for the Autonomous Outreach Agent Brain."""
    # 1. GET /api/v1/agent/status
    resp = client.get("/api/v1/agent/status", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "telemetry" in data
    assert data["live_send_enabled"] is False

    # 2. POST /api/v1/agent/seed-targets
    resp_seed = client.post("/api/v1/agent/seed-targets?target_city=Gangtok", headers=admin_auth_headers)
    assert resp_seed.status_code == 200
    seed_data = resp_seed.json()
    assert seed_data["seeded_count"] >= 2

    # 3. POST /api/v1/agent/run-cycle
    cycle_payload = {
        "target_city": "Gangtok",
        "channels": ["email"],
        "max_prospects": 2,
        "auto_approve_simulation": True,
    }
    resp_cycle = client.post("/api/v1/agent/run-cycle", json=cycle_payload, headers=admin_auth_headers)
    assert resp_cycle.status_code == 200
    cycle_res = resp_cycle.json()
    assert cycle_res["status"] == "completed"
    assert cycle_res["metrics"]["qualified"] >= 2


def test_agent_api_rbac_enforcement(client, auth_headers, admin_auth_headers):
    """Verifies RBAC rules on agent endpoints: sales_rep can view status, but only admin/manager can execute or seed."""
    # 1. Sales rep can view status
    resp = client.get("/api/v1/agent/status", headers=auth_headers)
    assert resp.status_code == 200

    # 2. Sales rep cannot seed targets (403 Forbidden)
    resp_seed = client.post("/api/v1/agent/seed-targets", headers=auth_headers)
    assert resp_seed.status_code == 403
    assert "Operation not permitted" in resp_seed.json()["detail"]

    # 3. Sales rep cannot trigger autonomous cycle (403 Forbidden)
    resp_cycle = client.post("/api/v1/agent/run-cycle", json={"target_city": "Siliguri"}, headers=auth_headers)
    assert resp_cycle.status_code == 403
    assert "Operation not permitted" in resp_cycle.json()["detail"]

    # 4. Unauthenticated request is rejected (401 Unauthorized)
    resp_unauth = client.get("/api/v1/agent/status")
    assert resp_unauth.status_code == 401


def test_background_task_worker_autonomous_cycle(db_session):
    """Verifies that Celery/background task worker can execute the autonomous cycle via execute_task_logic."""
    payload = {
        "target_city": "Patna",
        "channels": ["email"],
        "max_prospects": 2,
        "auto_approve_simulation": True,
        "user_id": 1,
    }
    res = execute_task_logic("autonomous_outreach_cycle", payload, db_session)
    assert res["status"] == "completed"
    assert res["metrics"]["prospects_discovered"] >= 2
