"""Phase 6 acceptance tests: Kill Switch, Campaign Lifecycle, Transactional Outbox & IST Follow-up Guard."""
from datetime import datetime, timezone, timedelta
from app.models.activity import AuditLog
from app.models.email import EmailDraft
from app.models.lead import Lead
from app.models.orchestration import OutboundDispatchOutbox
from app.services.email_sender_service import send_approved_email
from app.services.followup_service import process_autonomous_followups
from app.services.orchestration_service import is_within_ist_business_hours
from app.services.whatsapp_service import send_approved_whatsapp_message


def _create_approved_campaign_draft(client, admin_auth_headers, company_id: int):
    camp = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Phase 6 Orchestration Campaign",
            "objective": "Test campaign lifecycle and outbox controls",
            "target_city": "Siliguri",
            "daily_email_limit": 20,
        },
        headers=admin_auth_headers,
    ).json()

    client.post(
        f"/api/v1/campaigns/{camp['id']}/recipients",
        json={"company_ids": [company_id]},
        headers=admin_auth_headers,
    )
    client.post(
        f"/api/v1/campaigns/{camp['id']}/batch-draft",
        json={"tone": "Friendly professional"},
        headers=admin_auth_headers,
    )
    queue = client.get(f"/api/v1/approvals/queue?status=draft&campaign_id={camp['id']}", headers=admin_auth_headers).json()
    draft_id = queue["items"][0]["id"]
    client.post(f"/api/v1/approvals/approve/{draft_id}", headers=admin_auth_headers)
    return camp, draft_id


def test_global_kill_switch_halts_all_channels_and_restores_on_deactivate(
    client, db_session, admin_auth_headers, auth_headers, test_company
):
    camp, email_draft_id = _create_approved_campaign_draft(client, admin_auth_headers, test_company.id)

    # Also prepare an approved LinkedIn draft
    li_draft = client.post(
        "/api/v1/linkedin/draft",
        json={
            "company_id": test_company.id,
            "recipient_profile_url": "https://www.linkedin.com/in/phase6-exec",
            "message_type": "connection_note",
        },
        headers=admin_auth_headers,
    ).json()
    client.post(f"/api/v1/linkedin/approve/{li_draft['id']}", headers=admin_auth_headers)

    # Sales rep cannot toggle kill switch (403)
    assert client.post(
        "/api/v1/settings/kill-switch",
        json={"active": True, "reason": "Unauthorized attempt"},
        headers=auth_headers,
    ).status_code == 403

    # Admin activates Global Emergency Kill Switch
    on_resp = client.post(
        "/api/v1/settings/kill-switch",
        json={"active": True, "reason": "Incident response drill"},
        headers=admin_auth_headers,
    )
    assert on_resp.status_code == 200
    assert on_resp.json()["active"] is True

    # Audit log recorded
    audit = db_session.query(AuditLog).filter(AuditLog.action == "kill_switch_activated").first()
    assert audit is not None

    # 1. Direct email send blocked
    email_res = send_approved_email(db_session, email_draft_id, user_id=1)
    assert email_res.status == "blocked_kill_switch"

    # 2. Campaign dispatch blocked with HTTP 423 Locked
    camp_disp = client.post(f"/api/v1/campaigns/{camp['id']}/dispatch-approved", headers=admin_auth_headers)
    assert camp_disp.status_code == 423

    # 3. LinkedIn dispatch blocked
    li_disp = client.post(f"/api/v1/linkedin/dispatch/{li_draft['id']}", headers=admin_auth_headers)
    assert li_disp.status_code == 400
    assert "kill switch" in li_disp.json()["detail"].lower()

    # 4. Outbox processing halts immediately
    outbox_res = client.post("/api/v1/jobs/outbox/process", headers=admin_auth_headers)
    assert outbox_res.status_code == 200
    assert outbox_res.json()["halted_by_kill_switch"] is True

    # 5. Follow-up scheduler skips while kill switch is active
    fu_res = process_autonomous_followups(db_session, enforce_business_hours=False)
    assert fu_res["followups_generated"] == 0
    assert "kill_switch" in fu_res["skipped_reason"]

    # Deactivate kill switch -> dispatch works again
    off_resp = client.post(
        "/api/v1/settings/kill-switch",
        json={"active": False, "reason": "Drill complete"},
        headers=admin_auth_headers,
    )
    assert off_resp.status_code == 200
    assert off_resp.json()["active"] is False

    resumed_disp = client.post(f"/api/v1/campaigns/{camp['id']}/dispatch-approved", headers=admin_auth_headers)
    assert resumed_disp.status_code == 200
    assert resumed_disp.json()["simulated_count"] + resumed_disp.json()["sent_count"] == 1


def test_campaign_pause_resume_stop_lifecycle_and_outbox_cancellation(
    client, db_session, admin_auth_headers, test_company
):
    camp, draft_id = _create_approved_campaign_draft(client, admin_auth_headers, test_company.id)

    # Enqueue approved draft into transactional outbox (idempotent)
    enq1 = client.post(f"/api/v1/campaigns/{camp['id']}/enqueue-approved", headers=admin_auth_headers)
    assert enq1.status_code == 200
    assert enq1.json()["enqueued_count"] == 1

    # Calling enqueue again reuses same outbox row (no duplicate created)
    enq2 = client.post(f"/api/v1/campaigns/{camp['id']}/enqueue-approved", headers=admin_auth_headers)
    assert enq2.status_code == 200
    assert enq2.json()["outbox_ids"] == enq1.json()["outbox_ids"]
    assert db_session.query(OutboundDispatchOutbox).count() == 1

    # Pause campaign -> cancels pending outbox row & blocks dispatch (HTTP 409)
    pause_resp = client.post(f"/api/v1/campaigns/{camp['id']}/pause", headers=admin_auth_headers)
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "paused"
    assert pause_resp.json()["cancelled_outbox_items"] == 1

    blocked_disp = client.post(f"/api/v1/campaigns/{camp['id']}/dispatch-approved", headers=admin_auth_headers)
    assert blocked_disp.status_code == 409

    # Resume campaign -> transitions to 'active'
    resume_resp = client.post(f"/api/v1/campaigns/{camp['id']}/resume", headers=admin_auth_headers)
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "active"

    # Permanently stop campaign -> cannot be resumed or dispatched
    stop_resp = client.post(f"/api/v1/campaigns/{camp['id']}/stop", headers=admin_auth_headers)
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "stopped"

    bad_resume = client.post(f"/api/v1/campaigns/{camp['id']}/resume", headers=admin_auth_headers)
    assert bad_resume.status_code == 400
    assert client.post(f"/api/v1/campaigns/{camp['id']}/dispatch-approved", headers=admin_auth_headers).status_code == 409


def test_transactional_outbox_dispatches_exactly_once(client, db_session, admin_auth_headers, test_company):
    camp, draft_id = _create_approved_campaign_draft(client, admin_auth_headers, test_company.id)

    enq = client.post(f"/api/v1/campaigns/{camp['id']}/enqueue-approved", headers=admin_auth_headers)
    assert enq.status_code == 200
    assert enq.json()["enqueued_count"] == 1

    # Process outbox batch
    proc1 = client.post("/api/v1/jobs/outbox/process", headers=admin_auth_headers)
    assert proc1.status_code == 200
    assert proc1.json()["dispatched"] == 1

    # Outbox inspection shows status='dispatched'
    items = client.get("/api/v1/jobs/outbox", headers=admin_auth_headers).json()
    assert len(items) == 1
    assert items[0]["status"] == "dispatched"

    # Re-running process does NOT re-dispatch
    proc2 = client.post("/api/v1/jobs/outbox/process", headers=admin_auth_headers)
    assert proc2.status_code == 200
    assert proc2.json()["processed"] == 0


def test_ist_business_hours_guard_and_mandatory_draft_approval_in_followups(db_session, test_company):
    # Mark test_company lead as contacted 5 days ago so a follow-up is due
    lead = db_session.query(Lead).filter(Lead.company_id == test_company.id).first()
    if not lead:
        lead = Lead(company_id=test_company.id, pipeline_status="contacted", followup_count=0)
        db_session.add(lead)
    lead.pipeline_status = "contacted"
    lead.followup_count = 0
    lead.last_contact_date = datetime(2026, 11, 10, 6, 0, tzinfo=timezone.utc)
    db_session.commit()

    # 1. Outside IST business hours: Wednesday 2026-11-18 16:30 UTC == 22:00 IST
    night_ist_utc = datetime(2026, 11, 18, 16, 30, tzinfo=timezone.utc)
    ok_night, _ = is_within_ist_business_hours(now_utc=night_ist_utc)
    assert ok_night is False

    res_night = process_autonomous_followups(db_session, enforce_business_hours=True, now_override=night_ist_utc)
    assert res_night["followups_generated"] == 0
    assert "outside_ist_business_hours" in res_night["skipped_reason"]

    # 2. Sunday in IST: 2026-11-22 06:00 UTC == Sunday 11:30 IST
    sunday_utc = datetime(2026, 11, 22, 6, 0, tzinfo=timezone.utc)
    assert is_within_ist_business_hours(now_utc=sunday_utc)[0] is False

    # 3. Inside IST business hours: Wednesday 2026-11-18 05:30 UTC == 11:00 IST
    day_ist_utc = datetime(2026, 11, 18, 5, 30, tzinfo=timezone.utc)
    assert is_within_ist_business_hours(now_utc=day_ist_utc)[0] is True

    res_day = process_autonomous_followups(db_session, enforce_business_hours=True, now_override=day_ist_utc)
    assert res_day["followups_generated"] == 1
    created_draft = db_session.query(EmailDraft).filter(EmailDraft.company_id == test_company.id).order_by(EmailDraft.id.desc()).first()
    assert created_draft is not None
    # Mandatory human approval: MUST be in 'draft', NEVER auto-sent!
    assert created_draft.approval_status == "draft"
    assert created_draft.sent_at is None
