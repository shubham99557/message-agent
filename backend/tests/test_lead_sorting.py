from datetime import datetime, timedelta, timezone
from app.models.company import Company
from app.models.lead import Lead


def test_newest_first_lead_and_company_sorting(client, auth_headers, db_session):
    now = datetime.now(timezone.utc)

    # 1. Create older and newer companies with explicit timestamps
    old_comp = Company(
        name="Sort Old Tech Pvt Ltd",
        city="Siliguri",
        state="West Bengal",
        qualification_score=85.0,
        created_by_id=1,
        created_at=now - timedelta(days=5),
    )
    mid_comp = Company(
        name="Sort Mid Tech Pvt Ltd",
        city="Siliguri",
        state="West Bengal",
        qualification_score=60.0,
        created_by_id=1,
        created_at=now - timedelta(days=2),
    )
    new_comp = Company(
        name="Sort New Tech Pvt Ltd",
        city="Siliguri",
        state="West Bengal",
        qualification_score=40.0,
        created_by_id=1,
        created_at=now - timedelta(hours=1),
    )
    db_session.add_all([old_comp, mid_comp, new_comp])
    db_session.flush()

    old_lead = Lead(company_id=old_comp.id, pipeline_status="new", created_at=now - timedelta(days=5), updated_at=now - timedelta(days=5))
    new_lead = Lead(company_id=new_comp.id, pipeline_status="new", created_at=now - timedelta(hours=1), updated_at=now - timedelta(hours=1))
    db_session.add_all([old_lead, new_lead])
    db_session.commit()

    # Default companies order is newest_first
    res_def = client.get("/api/v1/companies?city=Siliguri&search=Sort ", headers=auth_headers)
    assert res_def.status_code == 200
    names_def = [item["name"] for item in res_def.json()["items"]]
    assert names_def == ["Sort New Tech Pvt Ltd", "Sort Mid Tech Pvt Ltd", "Sort Old Tech Pvt Ltd"]

    # 2. Manual lead creation appears at the top
    res_create = client.post(
        "/api/v1/companies",
        json={"name": "Sort Manual Top Co", "city": "Siliguri", "industry": "Software"},
        headers=auth_headers,
    )
    assert res_create.status_code == 201
    manual_id = res_create.json()["id"]

    res_after_manual = client.get("/api/v1/companies?city=Siliguri&search=Sort ", headers=auth_headers)
    assert res_after_manual.status_code == 200
    assert res_after_manual.json()["items"][0]["id"] == manual_id

    # 3. Editing an old company & old lead does NOT push it above newly created records
    res_edit_comp = client.put(
        f"/api/v1/companies/{old_comp.id}",
        json={"industry": "Updated Industry"},
        headers=auth_headers,
    )
    assert res_edit_comp.status_code == 200

    res_edit_lead = client.patch(
        f"/api/v1/crm/leads/{old_lead.id}/status",
        json={"status": "qualified", "notes": "Updated old lead"},
        headers=auth_headers,
    )
    assert res_edit_lead.status_code == 200

    res_comp_after_edit = client.get("/api/v1/companies?city=Siliguri&search=Sort ", headers=auth_headers)
    assert res_comp_after_edit.json()["items"][0]["id"] == manual_id

    res_leads_after_edit = client.get("/api/v1/crm/leads?city=Siliguri", headers=auth_headers)
    assert res_leads_after_edit.status_code == 200
    lead_ids = [item["id"] for item in res_leads_after_edit.json()["items"]]
    assert lead_ids.index(new_lead.id) < lead_ids.index(old_lead.id)

    # 4. Pagination preserves newest-first order
    p1 = client.get("/api/v1/companies?city=Siliguri&search=Sort &skip=0&limit=2", headers=auth_headers).json()["items"]
    p2 = client.get("/api/v1/companies?city=Siliguri&search=Sort &skip=2&limit=2", headers=auth_headers).json()["items"]
    assert [x["name"] for x in p1] == ["Sort Manual Top Co", "Sort New Tech Pvt Ltd"]
    assert [x["name"] for x in p2] == ["Sort Mid Tech Pvt Ltd", "Sort Old Tech Pvt Ltd"]

    # 5. Equal timestamps produce deterministic descending ID order
    tied_ts = now - timedelta(minutes=30)
    tie_a = Company(name="Sort Tie A", city="Patna", created_at=tied_ts)
    tie_b = Company(name="Sort Tie B", city="Patna", created_at=tied_ts)
    db_session.add_all([tie_a, tie_b])
    db_session.commit()
    res_tie = client.get("/api/v1/companies?city=Patna&search=Sort Tie", headers=auth_headers).json()["items"]
    assert [x["id"] for x in res_tie] == [tie_b.id, tie_a.id]

    # 6. Explicit user-selected sort options work server-side
    res_old = client.get("/api/v1/companies?city=Siliguri&search=Sort &sort_by=oldest_first", headers=auth_headers).json()["items"]
    assert res_old[0]["name"] == "Sort Old Tech Pvt Ltd"
    res_qual = client.get("/api/v1/companies?city=Siliguri&search=Sort &sort_by=qualification_desc", headers=auth_headers).json()["items"]
    assert res_qual[0]["name"] == "Sort Old Tech Pvt Ltd"
