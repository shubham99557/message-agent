def test_analytics_funnel_and_denominators(client, auth_headers, admin_auth_headers):
    # Create 2 real (non-demo) companies
    c1 = client.post(
        "/api/v1/companies",
        json={"name": "Siliguri Cloud Alpha", "city": "Siliguri", "public_email": "alpha@siliguricloud.in", "laptop_count_verified": 8, "laptop_count_evidence": "Office audit", "is_demo": False},
        headers=auth_headers
    ).json()

    c2 = client.post(
        "/api/v1/companies",
        json={"name": "Patna Software Beta", "city": "Patna", "public_email": "beta@patnasoft.in", "is_demo": False},
        headers=auth_headers
    ).json()

    # Draft emails for both
    d1 = client.post("/api/v1/emails/generate", json={"company_id": c1["id"]}, headers=auth_headers).json()
    d2 = client.post("/api/v1/emails/generate", json={"company_id": c2["id"]}, headers=auth_headers).json()

    # Check analytics: 2 drafted, 0 sent, 0 simulated!
    a1 = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()
    assert a1["emails_drafted"] >= 2
    initial_sent = a1["emails_sent"]
    initial_sim = a1["emails_simulated"]

    # Approve and dispatch ONLY ONE email in mock simulation mode
    client.post(f"/api/v1/approvals/approve/{d1['id']}", headers=admin_auth_headers)
    client.post(f"/api/v1/emails/send/{d1['id']}", headers=admin_auth_headers)

    # Check analytics again: simulated must increase by 1 while REAL emails_sent stays unchanged!
    a2 = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()
    assert a2["emails_sent"] == initial_sent
    assert a2["emails_simulated"] == initial_sim + 1
    assert a2["emails_drafted"] >= 2
    assert a2["emails_sent"] < a2["emails_drafted"]  # Drafted/simulated is NOT real sent!

    # Verify city breakdown includes all 4 target cities
    city_res = client.get("/api/v1/analytics/cities", headers=auth_headers)
    assert city_res.status_code == 200
    cities = {item["city"]: item for item in city_res.json()}
    assert "Siliguri" in cities
    assert "Gangtok" in cities
    assert "Patna" in cities
    assert "Bhagalpur" in cities
    assert cities["Siliguri"]["companies_count"] >= 1
