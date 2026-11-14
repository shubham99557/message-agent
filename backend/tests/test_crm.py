from datetime import datetime, timezone, timedelta


def test_crm_pipeline_and_lead_lifecycle(client, auth_headers):
    # 1. Create company
    comp_res = client.post(
        "/api/v1/companies",
        json={"name": "Bhagalpur Digital Services", "city": "Bhagalpur", "public_email": "sales@bhagalpurdigital.example.com"},
        headers=auth_headers
    )
    company_id = comp_res.json()["id"]

    # 2. Query CRM leads
    leads_res = client.get("/api/v1/crm/leads", headers=auth_headers)
    assert leads_res.status_code == 200
    leads = leads_res.json()["items"]
    lead = next(l for l in leads if l["company_id"] == company_id)
    assert lead["pipeline_status"] == "new"

    # 3. Transition lead through statuses
    status_update_res = client.patch(
        f"/api/v1/crm/leads/{lead['id']}/status",
        json={"status": "contacted", "notes": "Sent introductory email via approval queue"},
        headers=auth_headers
    )
    assert status_update_res.status_code == 200
    assert status_update_res.json()["pipeline_status"] == "contacted"

    # 4. Schedule meeting
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    meeting_res = client.post(
        f"/api/v1/crm/leads/{lead['id']}/meetings",
        json={"title": "ActTrident Demo & Architecture Review", "scheduled_at": future_time, "duration_minutes": 45},
        headers=auth_headers
    )
    assert meeting_res.status_code == 201
    assert meeting_res.json()["title"] == "ActTrident Demo & Architecture Review"

    # Lead status should now be meeting_scheduled
    lead_check = client.get(f"/api/v1/crm/leads/{lead['id']}", headers=auth_headers).json()
    assert lead_check["pipeline_status"] == "meeting_scheduled"

    # 5. Activate 90-day evaluation trial
    start_date = datetime.now(timezone.utc).isoformat()
    end_date = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
    trial_res = client.post(
        f"/api/v1/crm/leads/{lead['id']}/trials",
        json={"start_date": start_date, "end_date": end_date, "devices_count": 8},
        headers=auth_headers
    )
    assert trial_res.status_code == 201
    assert trial_res.json()["devices_count"] == 8

    lead_check_2 = client.get(f"/api/v1/crm/leads/{lead['id']}", headers=auth_headers).json()
    assert lead_check_2["pipeline_status"] == "trial_activated"
    assert lead_check_2["trial_status"] == "active"


def test_crm_opt_out_enforcement(client, auth_headers):
    # Create company with email
    comp_res = client.post(
        "/api/v1/companies",
        json={"name": "Opt-Out Corp", "city": "Siliguri", "public_email": "unsubscribe-me@optoutcorp.example.com"},
        headers=auth_headers
    )
    comp_data = comp_res.json()

    # Trigger opt-out
    opt_res = client.post(
        "/api/v1/crm/opt-out",
        json={"identifier": "unsubscribe-me@optoutcorp.example.com", "channel": "all", "reason": "unsubscribed_via_reply"},
        headers=auth_headers
    )
    assert opt_res.status_code == 200

    # Verify lead pipeline status is now "do_not_contact"
    leads_res = client.get("/api/v1/crm/leads", headers=auth_headers)
    lead = next(l for l in leads_res.json()["items"] if l["company_id"] == comp_data["id"])
    assert lead["pipeline_status"] == "do_not_contact"
