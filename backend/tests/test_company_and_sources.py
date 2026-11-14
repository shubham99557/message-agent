import io


def test_create_company_with_sources(client, auth_headers):
    payload = {
        "name": "North Bengal Infotech",
        "city": "Siliguri",
        "state": "West Bengal",
        "country": "India",
        "industry": "IT Services",
        "website": "https://nbinfotech.example.com",
        "public_email": "contact@nbinfotech.example.com",
        "public_phone": "+91-353-2500000",
        "public_whatsapp": "+91-9800000001",
        "laptop_count_verified": 12,
        "laptop_count_evidence": "Careers portal specifies standard issue Lenovo ThinkPads for all remote and hybrid engineers",
        "source_url": "https://nbinfotech.example.com/careers",
        "source_notes": "Official careers portal page"
    }

    res = client.post("/api/v1/companies", json=payload, headers=auth_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "North Bengal Infotech"
    assert data["has_verified_5_plus_laptops"] is True
    assert len(data["sources"]) >= 2
    assert any(s["field_name"] == "public_email" for s in data["sources"])
    assert any(s["field_name"] == "laptop_count" for s in data["sources"])


def test_laptop_verification_rule_enforcement(client, auth_headers):
    # If laptop count is 10 but NO evidence is provided, has_verified_5_plus_laptops must be False
    payload = {
        "name": "Unverified Hardware Ltd",
        "city": "Patna",
        "state": "Bihar",
        "laptop_count_verified": 10,
        "laptop_count_evidence": None
    }
    res = client.post("/api/v1/companies", json=payload, headers=auth_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["has_verified_5_plus_laptops"] is False


def test_csv_import_and_duplicate_detection(client, auth_headers):
    csv_data = """Company Name,City,State,Industry,Official Website,Public Email,Verified Laptops,Laptop Evidence
Sikkim Cloud Labs,Gangtok,Sikkim,Cloud Solutions,https://sikkimcloud.example.com,info@sikkimcloud.example.com,7,LinkedIn post showcasing office deployment of 7 MacBooks
Patna Devs Hub,Patna,Bihar,Software,https://patnadevs.example.com,hello@patnadevs.example.com,15,Official team photo showing 15 dedicated developer laptops
Sikkim Cloud Labs,Gangtok,Sikkim,Cloud Solutions,https://sikkimcloud.example.com,info@sikkimcloud.example.com,7,Duplicate row check
"""
    file_obj = io.BytesIO(csv_data.encode("utf-8"))
    res = client.post(
        "/api/v1/companies/import-csv",
        files={"file": ("companies.csv", file_obj, "text/csv")},
        headers=auth_headers
    )
    assert res.status_code == 200
    summary = res.json()
    assert summary["created_count"] == 2
    assert summary["updated_count"] == 1  # The duplicate was recognized and updated

    # Verify listing by city Gangtok
    list_res = client.get("/api/v1/companies?city=Gangtok", headers=auth_headers)
    assert list_res.status_code == 200
    gangtok_items = list_res.json()["items"]
    assert len(gangtok_items) == 1
    assert gangtok_items[0]["name"] == "Sikkim Cloud Labs"
    assert gangtok_items[0]["has_verified_5_plus_laptops"] is True
