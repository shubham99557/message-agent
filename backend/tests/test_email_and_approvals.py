from app.core.config import settings
from app.models.activity import SuppressionList


def test_ai_email_generation_5_tones_and_structure(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_90_DAY_EVALUATION_OFFER", True)
    # Create test company in Siliguri
    comp = client.post(
        "/api/v1/companies",
        json={
            "name": "Kanchenjunga Digital Studios",
            "city": "Siliguri",
            "industry": "Software Development",
            "laptop_count_verified": 10,
            "laptop_count_evidence": "10 dedicated developer workstations verified",
            "public_email": "hello@kanchenjungastudios.in",
            "decision_maker_name": "Debabrata Sengupta",
            "decision_maker_role": "Director of Engineering"
        },
        headers=auth_headers
    ).json()

    tones = ["Formal", "Friendly professional", "Technical", "Short introductory", "Follow-up"]

    for tone in tones:
        gen_res = client.post(
            "/api/v1/emails/generate",
            json={"company_id": comp["id"], "tone": tone},
            headers=auth_headers
        )
        assert gen_res.status_code == 201
        draft = gen_res.json()
        assert draft["tone"] == tone
        assert draft["approval_status"] == "draft"  # Default state is draft!
        assert "ActTrident" in draft["body_text"]
        assert "90-day" in draft["body_text"]
        assert "https://acttrident.ai/" in draft["body_text"]
        assert "Debabrata Sengupta" in draft["body_text"]


def test_human_approval_enforcement_and_sending(client, auth_headers, admin_auth_headers):
    comp = client.post(
        "/api/v1/companies",
        json={
            "name": "Sikkim Cloud Ops",
            "city": "Gangtok",
            "public_email": "security@sikkimcloudops.in"
        },
        headers=auth_headers
    ).json()

    # Generate draft
    draft_res = client.post(
        "/api/v1/emails/generate",
        json={"company_id": comp["id"], "tone": "Technical"},
        headers=auth_headers
    )
    draft = draft_res.json()
    draft_id = draft["id"]
    assert draft["approval_status"] == "draft"

    # Unauthorized sales_rep dispatch attempt -> MUST FAIL (403 RBAC)
    rep_send = client.post(f"/api/v1/emails/send/{draft_id}", headers=auth_headers)
    assert rep_send.status_code == 403

    # ATTEMPT TO SEND WITHOUT APPROVAL AS ADMIN -> MUST FAIL (MANDATORY APPROVAL RULE)
    unapproved_send = client.post(f"/api/v1/emails/send/{draft_id}", headers=admin_auth_headers)
    assert unapproved_send.status_code == 400
    assert "approved" in unapproved_send.json()["detail"]

    # Verify present in approval queue
    queue_res = client.get("/api/v1/approvals/queue?status=draft", headers=auth_headers)
    assert queue_res.status_code == 200
    queue_items = queue_res.json()["items"]
    assert any(item["id"] == draft_id for item in queue_items)

    # Standard rep approval attempt must fail (Role Restriction)
    rep_appr_res = client.post(f"/api/v1/approvals/approve/{draft_id}", headers=auth_headers)
    assert rep_appr_res.status_code == 403

    # Manager / Admin approves draft
    appr_res = client.post(f"/api/v1/approvals/approve/{draft_id}", headers=admin_auth_headers)
    assert appr_res.status_code == 200
    assert appr_res.json()["approval_status"] == "approved"

    # Now sending succeeds (dispatches live or simulated in mock mode)
    send_res = client.post(f"/api/v1/emails/send/{draft_id}", headers=admin_auth_headers)
    assert send_res.status_code == 200
    assert send_res.json()["status"] in ["sent", "simulated"]


def test_suppression_list_blocks_sending(client, auth_headers, admin_auth_headers, db_session):
    comp = client.post(
        "/api/v1/companies",
        json={"name": "Suppressed Tech", "city": "Patna", "public_email": "do-not-email@suppressed-test.in"},
        headers=auth_headers
    ).json()

    # Add to suppression list
    suppressed = SuppressionList(identifier="do-not-email@suppressed-test.in", channel="email", reason="Opted out")
    db_session.add(suppressed)
    db_session.commit()

    draft = client.post(
        "/api/v1/emails/generate",
        json={"company_id": comp["id"], "tone": "Friendly professional"},
        headers=auth_headers
    ).json()

    # Approve draft using admin credentials -> must be blocked because recipient is suppressed
    appr_res = client.post(f"/api/v1/approvals/approve/{draft['id']}", headers=admin_auth_headers)
    assert appr_res.status_code == 400

    # Attempt send -> must be blocked
    send_res = client.post(f"/api/v1/emails/send/{draft['id']}", headers=admin_auth_headers)
    assert send_res.status_code == 400
