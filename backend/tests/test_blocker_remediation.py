"""
Final Blocker Remediation Regression Test Suite (Fixes #1 through #13).
Every test targets a concrete defect identified in the Independent Verification Report.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
import httpx

from app.core.config import Settings, settings
from app.core.crypto import encrypt_secret
from app.core.security import create_access_token
from app.integrations.channel_adapter import get_channel_adapter
from app.integrations.gmail_adapter import sync_gmail_replies
from app.models.campaign import Campaign, CampaignRecipient
from app.models.channel import ChannelConnection
from app.models.company import Company
from app.models.email import EmailDraft, EmailEvent, EmailSendAttempt
from app.models.job import BackgroundTaskRecord, DeadLetterTask, TASK_CATEGORIES
from app.models.reply import Reply
from app.models.whatsapp import WhatsAppMessage, WhatsAppTemplate
from app.schemas.auth import UserCreate
from app.services import job_service
from app.services.auth_service import create_user
from app.services.email_sender_service import send_approved_email
from app.services.orchestration_service import set_kill_switch
from app.services.whatsapp_service import (
    approve_whatsapp_message_internal,
    create_whatsapp_message,
    record_contact_consent,
    seed_default_meta_templates,
    send_approved_whatsapp_message,
)
from app.schemas.whatsapp import ContactConsentCreate, WhatsAppDraftRequest
from app.worker.celery_app import celery_app
from app.worker.tasks import CATEGORY_TO_TASK, execute_task_logic, task_email_dispatch


def _make_sales_rep_headers(client, db_session, email: str, password: str = "SalesPass2026!"):
    user = create_user(
        db_session,
        UserCreate(email=email, password=password, full_name=email.split("@")[0], role="sales_rep"),
        role="sales_rep",
    )
    tok = client.post("/api/v1/auth/login", data={"username": email, "password": password}).json()["access_token"]
    return user, {"Authorization": f"Bearer {tok}"}


# --- FIX #1: Celery email_dispatch import & signature ---
def test_fix1_celery_email_dispatch_sync_and_eager_celery(client, db_session, admin_auth_headers, test_company):
    draft = client.post("/api/v1/emails/generate", json={"company_id": test_company.id}, headers=admin_auth_headers).json()
    client.post(f"/api/v1/approvals/approve/{draft['id']}", headers=admin_auth_headers)

    # 1. Execute via execute_task_logic (no ImportError for send_email; calls send_approved_email)
    res = execute_task_logic("email_dispatch", {"draft_id": draft["id"], "user_id": 1}, db_session)
    assert res["draft_id"] == draft["id"]
    assert res["result"]["status"] == "simulated"
    # Never record fake delivered event on simulation
    assert db_session.query(EmailEvent).filter(EmailEvent.draft_id == draft["id"], EmailEvent.event_type == "delivered").count() == 0

    # 2. Verify Celery eager task invocation works end-to-end
    draft2 = client.post("/api/v1/emails/generate", json={"company_id": test_company.id}, headers=admin_auth_headers).json()
    client.post(f"/api/v1/approvals/approve/{draft2['id']}", headers=admin_auth_headers)
    old_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    try:
        # Patch SessionLocal inside tasks module to reuse in-memory db_session
        import app.worker.tasks as worker_tasks
        orig_session = worker_tasks.SessionLocal

        class _NoCloseSessionProxy:
            def __getattr__(self, item):
                return getattr(db_session, item)

            def close(self):
                pass

        worker_tasks.SessionLocal = lambda: _NoCloseSessionProxy()
        try:
            async_res = task_email_dispatch.apply(args=[{"draft_id": draft2["id"], "user_id": 1}, "celery-eager-email-1"])
            assert async_res.successful()
            assert async_res.result["result"]["status"] == "simulated"
        finally:
            worker_tasks.SessionLocal = orig_session
    finally:
        celery_app.conf.task_always_eager = old_eager


# --- FIX #2: Nightly discovery NEVER inserts .example.com demo companies & demo prospects blocked from campaigns ---
def test_fix2_nightly_discovery_never_inserts_demo_and_campaigns_reject_demo(client, db_session, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    monkeypatch.setattr(settings, "SERPAPI_API_KEY", "")

    res = execute_task_logic("company_discovery", {"cities": ["Siliguri", "Gangtok", "Patna", "Bhagalpur"]}, db_session)
    assert res["new_companies_created"] == 0
    # Ensure zero .example.com companies were inserted
    assert db_session.query(Company).filter(Company.website.ilike("%.example.com%")).count() == 0

    # Demo company CANNOT enter campaigns
    demo_comp = client.post(
        "/api/v1/companies",
        json={"name": "Quarantined Demo Co", "website": "https://quarantined.example.com", "city": "Siliguri"},
        headers=admin_auth_headers,
    ).json()
    assert demo_comp["is_demo"] is True

    camp = client.post(
        "/api/v1/campaigns",
        json={"name": "Live Outreach Campaign", "objective": "Real prospects only", "target_city": "Siliguri"},
        headers=admin_auth_headers,
    ).json()
    add_res = client.post(
        f"/api/v1/campaigns/{camp['id']}/recipients",
        json={"company_ids": [demo_comp["id"]]},
        headers=admin_auth_headers,
    )
    assert add_res.status_code == 400
    assert "demo fixture" in add_res.json()["detail"].lower()


# --- FIX #3: Outbox processing & Gmail reply sync scheduled in Celery Beat ---
def test_fix3_outbox_and_gmail_sync_scheduled_and_executable(client, db_session, admin_auth_headers, test_company):
    assert "outbox_dispatch" in TASK_CATEGORIES
    assert "gmail_reply_sync" in TASK_CATEGORIES
    assert "outbox_dispatch" in CATEGORY_TO_TASK
    assert "gmail_reply_sync" in CATEGORY_TO_TASK
    assert "transactional-outbox-processor" in celery_app.conf.beat_schedule
    assert "gmail-reply-sync-poller" in celery_app.conf.beat_schedule

    # Gmail sync task handles disconnected state cleanly
    sync_res = execute_task_logic("gmail_reply_sync", {"max_results": 10}, db_session)
    assert sync_res["status"] == "skipped_disconnected"

    # Outbox dispatch task respects Kill Switch
    set_kill_switch(db_session, active=True, user_id=1, reason="Fix 3 test")
    ob_halted = execute_task_logic("outbox_dispatch", {"limit": 10, "user_id": 1}, db_session)
    assert ob_halted["halted_by_kill_switch"] is True
    set_kill_switch(db_session, active=False, user_id=1, reason="Fix 3 resume")


# --- FIX #4: Repair ALL broken WhatsAppChannelAdapter methods ---
def test_fix4_whatsapp_channel_adapter_all_methods_functional(db_session, test_company, monkeypatch):
    seed_default_meta_templates(db_session)
    monkeypatch.setattr(settings, "META_WA_ACCESS_TOKEN", "EAAB_test_token")
    monkeypatch.setattr(settings, "META_WA_PHONE_NUMBER_ID", "1000123456789")
    monkeypatch.setattr(settings, "META_APP_SECRET", "wa_adapter_secret_123")

    adapter = get_channel_adapter("whatsapp")

    # 1. connect() calls check_meta_connection_health(db=db, ...) cleanly
    def health_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"verified_name": "ActTrident", "display_phone_number": "+91 98320 00001", "quality_rating": "GREEN"})

    with httpx.Client(transport=httpx.MockTransport(health_handler)) as mock_http:
        health = adapter.connect(db_session, user_id=1, http_client=mock_http)
    assert health["status"] == "connected"
    assert health["verified_name"] == "ActTrident"

    # 2. prepare_message() uses WhatsAppDraftRequest & create_whatsapp_message cleanly
    record_contact_consent(
        db_session,
        ContactConsentCreate(
            company_id=test_company.id,
            contact_phone="+919832055555",
            consent_source="Website opt-in",
            consent_status="opted_in",
        ),
    )
    msg = adapter.prepare_message(
        db_session,
        company_id=test_company.id,
        payload={
            "recipient_phone": "+919832055555",
            "template_name": "acttrident_demo_invite",
            "parameters": {"1": "Rohan", "2": "Siliguri"},
        },
        user_id=1,
    )
    assert msg.id is not None
    assert msg.approval_status == "draft"

    # 3. process_webhook() invokes process_incoming_meta_webhook with real HMAC validation
    wh_payload = {"entry": []}
    raw_bytes = json.dumps(wh_payload, separators=(",", ":")).encode("utf-8")
    good_sig = "sha256=" + hmac.new(b"wa_adapter_secret_123", raw_bytes, hashlib.sha256).hexdigest()

    bad_wh = adapter.process_webhook(db_session, wh_payload, signature="sha256=bad")
    assert bad_wh["success"] is False

    good_wh = adapter.process_webhook(db_session, wh_payload, signature=good_sig)
    assert good_wh["success"] is True


# --- FIX #5: Analytics separates simulated vs sent, excludes demo, scopes campaign, counts real replies ---
def test_fix5_analytics_separates_simulated_from_sent_and_scopes_campaigns(client, db_session, admin_auth_headers):
    # Create 1 real company and 1 demo company
    real_c = client.post(
        "/api/v1/companies",
        json={"name": "Real Siliguri Firm", "website": "https://realsiliguri.in", "city": "Siliguri", "public_email": "info@realsiliguri.in", "is_demo": False},
        headers=admin_auth_headers,
    ).json()
    client.post(
        "/api/v1/companies",
        json={"name": "Hidden Demo Firm", "website": "https://hiddendemo.example.com", "city": "Siliguri", "public_email": "demo@hiddendemo.example.com"},
        headers=admin_auth_headers,
    )

    camp1 = client.post(
        "/api/v1/campaigns",
        json={"name": "Campaign One", "objective": "Obj 1", "target_city": "Siliguri"},
        headers=admin_auth_headers,
    ).json()
    camp2 = client.post(
        "/api/v1/campaigns",
        json={"name": "Campaign Two", "objective": "Obj 2", "target_city": "Patna"},
        headers=admin_auth_headers,
    ).json()
    client.post(f"/api/v1/campaigns/{camp1['id']}/recipients", json={"company_ids": [real_c["id"]]}, headers=admin_auth_headers)

    # Draft 1: Simulated send (must NOT increment real emails_sent!)
    d_sim = client.post("/api/v1/emails/generate", json={"company_id": real_c["id"], "campaign_id": camp1["id"]}, headers=admin_auth_headers).json()
    client.post(f"/api/v1/approvals/approve/{d_sim['id']}", headers=admin_auth_headers)
    client.post(f"/api/v1/emails/send/{d_sim['id']}", headers=admin_auth_headers)

    # Draft 2: Real provider sent + delivered + campaign reply
    d_real = client.post("/api/v1/emails/generate", json={"company_id": real_c["id"], "campaign_id": camp1["id"]}, headers=admin_auth_headers).json()
    draft_row = db_session.query(EmailDraft).filter(EmailDraft.id == d_real["id"]).first()
    draft_row.approval_status = "sent"
    draft_row.provider = "gmail"
    draft_row.provider_message_id = "gmail-real-id-001"
    db_session.add(EmailSendAttempt(draft_id=draft_row.id, attempt_number=1, idempotency_key="fix5-real-1", provider="gmail", outcome="sent", provider_message_id="gmail-real-id-001"))
    db_session.add(EmailEvent(draft_id=draft_row.id, event_type="delivered", details="Provider confirmed"))
    db_session.add(Reply(conversation_id=1, company_id=real_c["id"], campaign_id=camp1["id"], channel="email", sender_identifier="info@realsiliguri.in", recipient_identifier="outreach@acttrident.ai", message_body="Interested!", classification="interested"))
    db_session.commit()

    # Global dashboard: demo excluded, simulated separated from sent!
    dash = client.get("/api/v1/analytics/dashboard", headers=admin_auth_headers).json()
    assert dash["total_companies_researched"] == 1  # Demo excluded!
    assert dash["emails_sent"] == 1                 # ONLY real sent, NOT simulated!
    assert dash["emails_simulated"] == 1            # Tracked separately!
    assert dash["emails_accepted"] == 1
    assert dash["emails_delivered"] == 1
    assert dash["replies_received"] == 1

    # Campaign 2 scoped dashboard must see 0 replies, 0 delivered, 0 sent (not global leak!)
    dash_c2 = client.get(f"/api/v1/analytics/dashboard?campaign_id={camp2['id']}", headers=admin_auth_headers).json()
    assert dash_c2["emails_sent"] == 0
    assert dash_c2["emails_delivered"] == 0
    assert dash_c2["replies_received"] == 0

    # Campaign summary reports genuine reply count (NOT hardcoded 0!)
    camp_summaries = {c["campaign_id"]: c for c in client.get("/api/v1/analytics/campaigns", headers=admin_auth_headers).json()}
    assert camp_summaries[camp1["id"]]["replies"] == 1
    assert camp_summaries[camp2["id"]]["replies"] == 0


# --- FIX #6: Gmail bounce event deduplication ---
def test_fix6_gmail_bounce_sync_is_idempotent(db_session, test_company):
    conn = ChannelConnection(
        channel="gmail",
        account_identifier="outreach@acttrident.ai",
        status="connected",
        encrypted_access_token=encrypt_secret("valid-gmail-tok"),
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(conn)
    draft = EmailDraft(
        company_id=test_company.id,
        recipient_email="bounced@prospect.in",
        subject="ActTrident Eval",
        body_html="<p>Hi</p>",
        body_text="Hi",
        approval_status="sent",
        provider="gmail",
        provider_message_id="gmsg-orig-1",
        provider_thread_id="gthread-bounce-1",
    )
    db_session.add(draft)
    db_session.commit()

    def bounce_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"messages": [{"id": "gbounce-msg-999"}]})
        if request.url.path.endswith("/messages/gbounce-msg-999"):
            return httpx.Response(
                200,
                json={
                    "id": "gbounce-msg-999",
                    "threadId": "gthread-bounce-1",
                    "snippet": "Address not found: bounced@prospect.in",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Mail Delivery Subsystem <mailer-daemon@googlemail.com>"},
                            {"name": "Subject", "value": "Delivery Status Notification (Failure)"},
                            {"name": "To", "value": "outreach@acttrident.ai"},
                        ]
                    },
                },
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(bounce_handler)) as mock_http:
        r1 = sync_gmail_replies(db_session, conn, http_client=mock_http)
        r2 = sync_gmail_replies(db_session, conn, http_client=mock_http)

    assert r1["bounces_recorded"] == 1
    assert r2["bounces_recorded"] == 0
    assert r2["skipped_duplicates"] == 1
    assert db_session.query(EmailEvent).filter(EmailEvent.draft_id == draft.id, EmailEvent.event_type == "bounced").count() == 1


# --- FIX #7: Per-minute & daily sending limits enforced on sync and async dispatch ---
def test_fix7_rate_limits_enforced_on_sync_email_and_whatsapp(client, db_session, admin_auth_headers, test_company, monkeypatch):
    # 1. Email per-minute limit = 1 -> 2nd synchronous HTTP send returns 429
    monkeypatch.setattr(settings, "OUTBOUND_RATE_LIMIT_EMAIL_PER_MIN", 1)
    d1 = client.post("/api/v1/emails/generate", json={"company_id": test_company.id}, headers=admin_auth_headers).json()
    d2 = client.post("/api/v1/emails/generate", json={"company_id": test_company.id}, headers=admin_auth_headers).json()
    client.post(f"/api/v1/approvals/approve/{d1['id']}", headers=admin_auth_headers)
    client.post(f"/api/v1/approvals/approve/{d2['id']}", headers=admin_auth_headers)

    assert client.post(f"/api/v1/emails/send/{d1['id']}", headers=admin_auth_headers).status_code == 200
    r2 = client.post(f"/api/v1/emails/send/{d2['id']}", headers=admin_auth_headers)
    assert r2.status_code == 429
    assert "rate limit" in r2.json()["detail"].lower()

    # 2. WhatsApp per-minute limit = 1 AND daily limit = 1
    seed_default_meta_templates(db_session)
    record_contact_consent(
        db_session,
        ContactConsentCreate(company_id=test_company.id, contact_phone="+919832077777", consent_source="Web", consent_status="opted_in"),
    )
    monkeypatch.setattr(settings, "OUTBOUND_RATE_LIMIT_WA_PER_MIN", 1)
    w1 = create_whatsapp_message(db_session, test_company, WhatsAppDraftRequest(company_id=test_company.id, recipient_phone="+919832077777", template_name="acttrident_demo_invite", parameters={"1": "A", "2": "Siliguri"}))
    w2 = create_whatsapp_message(db_session, test_company, WhatsAppDraftRequest(company_id=test_company.id, recipient_phone="+919832077777", template_name="acttrident_demo_invite", parameters={"1": "B", "2": "Siliguri"}))
    approve_whatsapp_message_internal(db_session, w1, user_id=1)
    approve_whatsapp_message_internal(db_session, w2, user_id=1)

    ok1, _ = send_approved_whatsapp_message(db_session, w1.id, user_id=1)
    ok2, msg2 = send_approved_whatsapp_message(db_session, w2.id, user_id=1)
    assert ok1 is True
    assert ok2 is False
    assert "rate limit" in msg2.lower()

    # Daily WhatsApp limit enforcement
    job_service.reset_rate_limit("whatsapp_dispatch")
    monkeypatch.setattr(settings, "OUTBOUND_RATE_LIMIT_WA_PER_MIN", 10)
    monkeypatch.setattr(settings, "DEFAULT_DAILY_WHATSAPP_LIMIT", 1)
    w1.approval_status = "sent"
    w1.sent_at = datetime.now(timezone.utc)
    db_session.commit()
    ok3, msg3 = send_approved_whatsapp_message(db_session, w2.id, user_id=1)
    assert ok3 is False
    assert "daily whatsapp sending limit" in msg3.lower()


# --- FIX #8: Synchronous retry behavior & safe DLQ escalation ---
def test_fix8_synchronous_task_retries_then_succeeds_or_dead_letters(db_session, monkeypatch):
    import app.worker.tasks as worker_tasks

    # Case A: Transient failure twice, succeeds on 3rd attempt
    attempts = {"count": 0}

    def flaky_logic(category, payload, db):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("Transient network blip")
        return {"ok": True, "attempt": attempts["count"]}

    monkeypatch.setattr(worker_tasks, "execute_task_logic", flaky_logic)
    rec = job_service.create_background_task(
        db=db_session,
        category="daily_reporting",
        payload={},
        max_retries=3,
        execute_sync=True,
    )
    assert rec.status == "completed"
    assert rec.retry_count == 2
    assert db_session.query(DeadLetterTask).filter(DeadLetterTask.task_id == rec.task_id).count() == 0

    # Case B: Persistent failure exhausts retries -> moves safely to dead_letter + DeadLetterTask
    def always_fail(category, payload, db):
        raise RuntimeError("Permanent provider outage")

    monkeypatch.setattr(worker_tasks, "execute_task_logic", always_fail)
    failed_rec = job_service.create_background_task(
        db=db_session,
        category="daily_reporting",
        payload={},
        max_retries=2,
        execute_sync=True,
    )
    assert failed_rec.status == "dead_letter"
    assert failed_rec.retry_count == 2
    dlq = db_session.query(DeadLetterTask).filter(DeadLetterTask.task_id == failed_rec.task_id).first()
    assert dlq is not None
    assert dlq.retries_exhausted == 2


# --- FIX #9: Reject JWT tokens missing token-version ('tv') claim ---
def test_fix9_jwt_missing_token_version_claim_is_rejected(client, db_session, test_sales_user):
    legacy_token = create_access_token(data={"sub": test_sales_user.email, "role": test_sales_user.role, "user_id": test_sales_user.id})
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {legacy_token}"})
    assert resp.status_code == 401
    assert "token version" in resp.json()["detail"].lower() or "revoked" in resp.json()["detail"].lower()


# --- FIX #10: No hardcoded WA verify token in frontend & strict production validation ---
def test_fix10_no_hardcoded_wa_verify_token_and_prod_security_guards():
    root = Path(__file__).resolve().parents[2]
    ui_text = (root / "frontend" / "src" / "views" / "IntegrationsView.tsx").read_text(encoding="utf-8")
    assert "acttrident_meta_webhook_secret_2026" not in ui_text

    # Production with live WhatsApp token MUST reject default META_WA_VERIFY_TOKEN & missing META_APP_SECRET
    prod_base = dict(
        ENVIRONMENT="production",
        SECRET_KEY="A" * 40,
        CREDENTIAL_ENCRYPTION_KEY="B" * 32,
        DATABASE_URL="postgresql://acttrident:strongpass@postgres:5432/acttrident_db",
        BACKEND_CORS_ORIGINS=["https://outreach.acttrident.ai"],
        WHATSAPP_ENABLED=True,
        META_WA_ACCESS_TOKEN="EAAB_live_token",
        META_APP_SECRET="",
        META_WA_VERIFY_TOKEN="acttrident_meta_webhook_secret_2026",
    )
    s_no_secret = Settings(**prod_base)
    try:
        s_no_secret.validate_production_security()
        assert False, "Expected ValueError for missing META_APP_SECRET"
    except ValueError as exc:
        assert "META_APP_SECRET" in str(exc)

    prod_base["META_APP_SECRET"] = "real_meta_app_secret"
    s_default_verify = Settings(**prod_base)
    try:
        s_default_verify.validate_production_security()
        assert False, "Expected ValueError for default META_WA_VERIFY_TOKEN"
    except ValueError as exc:
        assert "META_WA_VERIFY_TOKEN" in str(exc)


# --- FIX #11: Company & Email-Draft ownership/role restrictions ---
def test_fix11_company_and_email_draft_ownership_enforced(client, db_session, admin_auth_headers):
    _, rep_a_headers = _make_sales_rep_headers(client, db_session, "rep_a@acttrident.ai")
    _, rep_b_headers = _make_sales_rep_headers(client, db_session, "rep_b@acttrident.ai")

    comp_a = client.post(
        "/api/v1/companies",
        json={"name": "Rep A Real Prospect", "website": "https://repaprospect.in", "city": "Siliguri", "public_email": "ceo@repaprospect.in", "is_demo": False},
        headers=rep_a_headers,
    ).json()
    draft_a = client.post("/api/v1/emails/generate", json={"company_id": comp_a["id"]}, headers=rep_a_headers).json()

    # Sales Rep B CANNOT edit, verify, attach sources to, or inspect/edit Rep A's company or draft
    assert client.put(f"/api/v1/companies/{comp_a['id']}", json={"industry": "Hijacked"}, headers=rep_b_headers).status_code == 403
    assert client.post(f"/api/v1/companies/{comp_a['id']}/verify", json={"verification_status": "verified", "verification_method": "manual"}, headers=rep_b_headers).status_code == 403
    assert client.post(f"/api/v1/companies/{comp_a['id']}/sources", json={"company_id": comp_a["id"], "field_name": "website", "source_url": "https://repaprospect.in", "source_type": "official_website"}, headers=rep_b_headers).status_code == 403
    assert client.put(f"/api/v1/emails/drafts/{draft_a['id']}", json={"subject": "Hijacked"}, headers=rep_b_headers).status_code == 403
    assert client.get(f"/api/v1/emails/drafts/{draft_a['id']}/attempts", headers=rep_b_headers).status_code == 403

    # Owner (Rep A) and Admin CAN edit draft; editing already-sent draft is blocked (400)
    assert client.put(f"/api/v1/emails/drafts/{draft_a['id']}", json={"subject": "Updated by Rep A"}, headers=rep_a_headers).status_code == 200
    assert client.post(f"/api/v1/companies/{comp_a['id']}/verify", json={"verification_status": "verified", "verification_method": "manual"}, headers=admin_auth_headers).status_code == 200

    row = db_session.query(EmailDraft).filter(EmailDraft.id == draft_a["id"]).first()
    row.approval_status = "sent"
    db_session.commit()
    assert client.put(f"/api/v1/emails/drafts/{draft_a['id']}", json={"subject": "Edit after sent"}, headers=admin_auth_headers).status_code == 400


# --- FIX #12 & #13: Dockerfile, Deployment Guide, and Docker Compose consistency ---
def test_fix12_and_fix13_docker_and_deployment_guide_alignment():
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "docker" / "Dockerfile.backend").read_text(encoding="utf-8")
    deploy_guide = (root / "DEPLOYMENT_GUIDE.md").read_text(encoding="utf-8")
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")

    assert "postgresql-client" in dockerfile
    assert "/app/alembic.ini" in deploy_guide
    assert "/app/scripts/provision_admin.py" in deploy_guide
    assert "/app/backend/alembic.ini" not in deploy_guide
    assert "/app/backend/scripts/provision_admin.py" not in deploy_guide
    assert "redis-cli" in compose
    assert "CREDENTIAL_ENCRYPTION_KEY" in compose
