from app.models.activity import AuditLog


def test_campaign_scheduling_and_batch_processing(client, auth_headers):
    # 1. Create a campaign targeting Siliguri
    camp_res = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Siliguri IT Companies Outreach Q1",
            "objective": "Acquire B2B customers for ActTrident 90-day evaluation",
            "target_city": "Siliguri",
            "daily_email_limit": 25,
            "daily_whatsapp_limit": 10,
            "sending_schedule": "09:00-18:00 IST Weekdays"
        },
        headers=auth_headers
    )
    assert camp_res.status_code == 201
    campaign = camp_res.json()
    camp_id = campaign["id"]
    assert campaign["status"] == "draft"  # All campaigns must default to draft!

    # 2. Add real non-demo recipient
    c1 = client.post(
        "/api/v1/companies",
        json={"name": "Siliguri Cloud Alpha 2", "city": "Siliguri", "public_email": "alpha2@siliguricloud.in", "is_demo": False},
        headers=auth_headers
    ).json()

    rec_res = client.post(
        f"/api/v1/campaigns/{camp_id}/recipients",
        json={"company_ids": [c1["id"]]},
        headers=auth_headers
    )
    assert rec_res.status_code == 200
    assert rec_res.json()["added_recipients"] == 1

    # 3. Generate drafts for campaign
    draft_gen_res = client.post(
        f"/api/v1/campaigns/{camp_id}/generate-drafts",
        json={"tone": "Technical"},
        headers=auth_headers
    )
    assert draft_gen_res.status_code == 200
    assert draft_gen_res.json()["drafts_created"] == 1

    # 4. Campaign status retrieval
    camp_check = client.get(f"/api/v1/campaigns/{camp_id}", headers=auth_headers).json()
    assert camp_check["emails_drafted"] == 1
    assert camp_check["emails_sent"] == 0  # Still 0 sent because unapproved!


def test_api_failure_handling_and_permissions(client, auth_headers, admin_auth_headers, db_session):
    # 1. Non-existent company 404
    res_404 = client.get("/api/v1/companies/99999", headers=auth_headers)
    assert res_404.status_code == 404

    # 2. Malformed CSV upload 400
    res_csv = client.post(
        "/api/v1/companies/import-csv",
        files={"file": ("malformed.txt", b"invalid data", "text/plain")},
        headers=auth_headers
    )
    assert res_csv.status_code == 400

    # 3. Nonexistent WhatsApp template validation
    comp = client.post(
        "/api/v1/companies",
        json={"name": "Template Test Corp", "city": "Patna", "public_phone": "+91-9431099999"},
        headers=auth_headers
    ).json()

    res_tmpl_fail = client.post(
        "/api/v1/whatsapp/draft",
        json={"company_id": comp["id"], "template_name": "unapproved_random_template_xyz"},
        headers=auth_headers
    )
    assert res_tmpl_fail.status_code == 400
    assert "not found or not approved" in res_tmpl_fail.json()["detail"].lower()

    # 4. Security Audit Log recording
    audit_logs_res = client.get("/api/v1/settings/audit-logs", headers=admin_auth_headers)
    assert audit_logs_res.status_code == 200
    logs = audit_logs_res.json()
    assert len(logs) >= 1
