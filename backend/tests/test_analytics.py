def test_analytics_funnel_and_denominators(client, auth_headers, admin_auth_headers):
    # Create 2 companies
    c1 = client.post(
        "/api/v1/companies",
        json={"name": "Siliguri Cloud Alpha", "city": "Siliguri", "public_email": "alpha@siliguricloud.example.com", "laptop_count_verified": 8, "laptop_count_evidence": "Office audit"},
        headers=auth_headers
    ).json()

    c2 = client.post(
        "/api/v1/companies",
        json={"name": "Patna Software Beta", "city": "Patna", "public_email": "beta@patnasoft.example.com"},
        headers=auth_headers
    ).json()

    # Draft emails for both
    d1 = client.post("/api/v1/emails/generate", json={"company_id": c1["id"]}, headers=auth_headers).json()
    d2 = client.post("/api/v1/emails/generate", json={"company_id": c2["id"]}, headers=auth_headers).json()

    # Check analytics: 2 drafted, but 0 sent!
    a1 = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()
    assert a1["emails_drafted"] >= 2
    initial_sent = a1["emails_sent"]

    # Approve and send ONLY ONE email using admin credentials
    client.post(f"/api/v1/approvals/approve/{d1['id']}", headers=admin_auth_headers)
    client.post(f"/api/v1/emails/send/{d1['id']}", headers=admin_auth_headers)

    # Check analytics again: sent count must increase by exactly 1, NEVER 2!
    a2 = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()
    assert a2["emails_sent"] == initial_sent + 1
    assert a2["emails_drafted"] >= 2
    assert a2["emails_sent"] < a2["emails_drafted"]  # Drafted is NOT sent!

    # Verify city breakdown includes all 4 target cities
    city_res = client.get("/api/v1/analytics/cities", headers=auth_headers)
    assert city_res.status_code == 200
    cities = {item["city"]: item for item in city_res.json()}
    assert "Siliguri" in cities
    assert "Gangtok" in cities
    assert "Patna" in cities
    assert "Bhagalpur" in cities
    assert cities["Siliguri"]["companies_count"] >= 1
