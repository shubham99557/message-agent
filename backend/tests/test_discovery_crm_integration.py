from datetime import datetime, timezone
from unittest.mock import patch
import httpx

from app.integrations.discovery_adapters import (
    OpenStreetMapPublicAdapter,
    SerpApiDiscoveryAdapter,
    TavilyDiscoveryAdapter,
)
from app.models.company import ContactSource
from app.models.lead import Lead
from app.schemas.research import DiscoveredCompanyItem, DiscoveryQuery
from app.services.discovery_service import search_public_company_directory_paginated


def _make_item(name: str, city: str = "Chennai", website: str = "https://example-real.in") -> dict:
    return {
        "name": name,
        "website": website,
        "industry": "Software Development",
        "city": city,
        "state": "Tamil Nadu",
        "country": "India",
        "source_url": f"https://www.openstreetmap.org/node/{abs(hash(name)) % 100000}",
        "source_type": "openstreetmap_public",
        "confidence_level": 0.72,
        "is_demo": False,
        "verification_status": "unverified",
        "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def test_discovery_import_persists_provenance_qualifies_and_appears_first(client, auth_headers, db_session):
    payload = _make_item("Chennai Cloud Works Pvt Ltd", website="https://chennaicloud.in")
    r_imp = client.post("/api/v1/discovery/import", json=payload, headers=auth_headers)
    assert r_imp.status_code == 201, r_imp.text
    created = r_imp.json()
    assert created["name"] == "Chennai Cloud Works Pvt Ltd"
    # Qualification runs automatically on import
    assert created["qualification_score"] > 0
    assert created["qualification_status"] is not None

    # Lead & ContactSource exist in CRM
    lead = db_session.query(Lead).filter(Lead.company_id == created["id"]).first()
    assert lead is not None
    src = db_session.query(ContactSource).filter(ContactSource.company_id == created["id"]).first()
    assert src is not None

    # Appears at top of GET /companies
    r_list = client.get("/api/v1/companies?city=Chennai", headers=auth_headers)
    assert r_list.status_code == 200
    assert r_list.json()["items"][0]["id"] == created["id"]

    # Duplicate import is rejected cleanly
    r_dup = client.post("/api/v1/discovery/import", json=payload, headers=auth_headers)
    assert r_dup.status_code == 400


def test_batch_import_summary_counts_saved_and_duplicates(client, auth_headers):
    item_new = _make_item("Madurai Systems Ltd", city="Madurai", website="https://maduraisys.in")
    r1 = client.post("/api/v1/discovery/import", json=item_new, headers=auth_headers)
    assert r1.status_code == 201

    item_fresh = _make_item("Coimbatore AI Labs", city="Coimbatore", website="https://coimbatoreai.in")
    r_batch = client.post(
        "/api/v1/discovery/batch-import-summary",
        json={"companies": [item_new, item_fresh]},
        headers=auth_headers,
    )
    assert r_batch.status_code == 200, r_batch.text
    summary = r_batch.json()
    assert summary["total_submitted"] == 2
    assert summary["saved_count"] == 1
    assert summary["duplicates_skipped"] == 1
    assert summary["failed_count"] == 0
    assert summary["skipped_names"] == ["Madurai Systems Ltd"]


def test_discovery_handles_empty_missing_keys_and_api_failures():
    # Missing API keys report unconfigured honestly without crashing
    with patch("app.integrations.discovery_adapters.settings.TAVILY_API_KEY", ""), \
         patch("app.integrations.discovery_adapters.settings.SERPAPI_API_KEY", ""):
        assert TavilyDiscoveryAdapter().is_configured() is False
        assert SerpApiDiscoveryAdapter().is_configured() is False

    # External timeout / empty results do not fabricate fake companies
    with patch.object(OpenStreetMapPublicAdapter, "search", side_effect=httpx.TimeoutException("timeout")):
        res = search_public_company_directory_paginated(
            DiscoveryQuery(city="NonExistentZetaCity", industry="Software", page=1, page_size=10)
        )
        assert res.total == 0
        assert res.items == []


def test_discovery_pagination_and_sorting():
    fake_items = [
        DiscoveredCompanyItem(name="Alpha Soft", city="Pune", state="Maharashtra", country="India", source_url="https://a.in", source_type="openstreetmap_public", confidence_level=0.5),
        DiscoveredCompanyItem(name="Beta Soft", city="Pune", state="Maharashtra", country="India", source_url="https://b.in", source_type="openstreetmap_public", confidence_level=0.9),
        DiscoveredCompanyItem(name="Gamma Soft", city="Pune", state="Maharashtra", country="India", source_url="https://c.in", source_type="openstreetmap_public", confidence_level=0.7),
    ]
    with patch("app.services.discovery_service.search_public_company_directory", return_value=fake_items):
        p1 = search_public_company_directory_paginated(DiscoveryQuery(city="Pune", page=1, page_size=2, sort_by="confidence", sort_order="desc"))
        p2 = search_public_company_directory_paginated(DiscoveryQuery(city="Pune", page=2, page_size=2, sort_by="confidence", sort_order="desc"))
        assert p1.total == 3
        assert p1.total_pages == 2
        assert [x.name for x in p1.items] == ["Beta Soft", "Gamma Soft"]
        assert [x.name for x in p2.items] == ["Alpha Soft"]
