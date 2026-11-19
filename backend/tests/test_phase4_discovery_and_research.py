"""Phase 4 acceptance tests: Real Lead Discovery, Provenance, Verification & Honest Research."""
import json
import httpx
from app.core.config import settings
from app.integrations.discovery_adapters import (
    OpenStreetMapPublicAdapter,
    SerpApiDiscoveryAdapter,
    TavilyDiscoveryAdapter,
)
from app.models.activity import AuditLog
from app.models.company import Company
from app.schemas.research import DiscoveryQuery


def test_discovery_quarantines_demo_fixtures_and_respects_include_demo(client, admin_auth_headers, monkeypatch):
    # 1. With include_demo=True in non-production, every .example.com item is strictly tagged demo_fixture
    resp_demo = client.post(
        "/api/v1/discovery/search",
        json={"city": "Siliguri", "min_devices": 5, "include_demo": True},
        headers=admin_auth_headers,
    )
    assert resp_demo.status_code == 200
    items = resp_demo.json()
    assert len(items) >= 1
    for item in items:
        assert item["is_demo"] is True
        assert item["verification_status"] == "demo_fixture"
        assert item["source_type"] == "demo_fixture"

    # 2. With include_demo=False (and no search API keys configured), zero demo fixtures are returned
    monkeypatch.setattr(settings, "TAVILY_API_KEY", None)
    monkeypatch.setattr(settings, "SERPAPI_API_KEY", None)
    resp_real = client.post(
        "/api/v1/discovery/search",
        json={"city": "Siliguri", "min_devices": 5, "include_demo": False},
        headers=admin_auth_headers,
    )
    assert resp_real.status_code == 200
    assert resp_real.json() == []

    # 3. In production environment, demo fixtures are NEVER returned even if include_demo=True
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    resp_prod = client.post(
        "/api/v1/discovery/search",
        json={"city": "Siliguri", "min_devices": 5, "include_demo": True},
        headers=admin_auth_headers,
    )
    assert resp_prod.status_code == 200
    assert resp_prod.json() == []


def test_discovery_sources_endpoint_reports_honest_adapter_status(client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "TAVILY_API_KEY", None)
    monkeypatch.setattr(settings, "SERPAPI_API_KEY", "serp-test-key")
    resp = client.get("/api/v1/discovery/sources", headers=admin_auth_headers)
    assert resp.status_code == 200
    sources = {s["name"]: s for s in resp.json()["sources"]}
    assert sources["tavily_search"]["configured"] is False
    assert sources["serpapi_search"]["configured"] is True
    assert sources["openstreetmap_nominatim"]["configured"] is True
    for s in sources.values():
        assert s["is_demo_source"] is False


def test_real_discovery_adapters_never_invent_laptop_counts_and_filter_demo_domains(monkeypatch):
    import app.integrations.discovery_adapters as da

    monkeypatch.setattr(settings, "TAVILY_API_KEY", "tvly-test-key")
    monkeypatch.setattr(settings, "SERPAPI_API_KEY", "serp-test-key")
    # Deterministic offline URL safety check (still rejects loopback/private URLs without live DNS)
    monkeypatch.setattr(
        da,
        "is_safe_external_url",
        lambda u: u.startswith("https://") and "127.0.0.1" not in u and "localhost" not in u,
    )
    query = DiscoveryQuery(city="Siliguri", industry="Software Development")

    # 1. Tavily adapter via MockTransport (filters out .example.com AND private SSRF URLs)
    def tavily_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "North Bengal Cloud Pvt Ltd - Official Website",
                        "url": "https://northbengalcloud.in",
                        "content": "Custom software engineering in Siliguri.",
                    },
                    {
                        "title": "Fake Demo Co",
                        "url": "https://fakedemo.example.com",
                        "content": "Should be filtered out.",
                    },
                    {
                        "title": "Internal Metadata",
                        "url": "http://127.0.0.1:8000/secret",
                        "content": "Should be blocked by SSRF check.",
                    },
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(tavily_handler)) as mock_http:
        tavily_items = TavilyDiscoveryAdapter().search(query, http_client=mock_http)
    assert len(tavily_items) == 1
    assert tavily_items[0].name == "North Bengal Cloud Pvt Ltd"
    assert tavily_items[0].is_demo is False
    assert tavily_items[0].verification_status == "unverified"
    assert tavily_items[0].laptop_count_verified is None
    assert tavily_items[0].source_type == "tavily_search"
    assert tavily_items[0].source_url == "https://northbengalcloud.in"
    assert tavily_items[0].retrieval_timestamp is not None

    # 2. SerpAPI adapter via MockTransport
    def serp_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "organic_results": [
                    {
                        "title": "Sikkim Tech Works | Gangtok IT",
                        "link": "https://sikkimtechworks.co.in",
                        "snippet": "IT services firm in Gangtok.",
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(serp_handler)) as mock_http:
        serp_items = SerpApiDiscoveryAdapter().search(DiscoveryQuery(city="Gangtok"), http_client=mock_http)
    assert len(serp_items) == 1
    assert serp_items[0].is_demo is False
    assert serp_items[0].verification_status == "unverified"
    assert serp_items[0].laptop_count_verified is None
    assert serp_items[0].source_type == "serpapi_search"

    # 3. OpenStreetMap public adapter via MockTransport
    def osm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "osm_type": "node",
                    "osm_id": 991122,
                    "name": "Patna Infotech Hub",
                    "display_name": "Patna Infotech Hub, Boring Road, Patna, Bihar, India",
                    "address": {"city": "Patna", "state": "Bihar"},
                    "extratags": {
                        "office": "it",
                        "website": "https://patnainfotechhub.in",
                        "email": "info@patnainfotechhub.in",
                    },
                }
            ],
        )

    with httpx.Client(transport=httpx.MockTransport(osm_handler)) as mock_http:
        osm_items = OpenStreetMapPublicAdapter().search(DiscoveryQuery(city="Patna"), http_client=mock_http)
    assert len(osm_items) == 1
    assert osm_items[0].name == "Patna Infotech Hub"
    assert osm_items[0].public_email == "info@patnainfotechhub.in"
    assert osm_items[0].laptop_count_verified is None
    assert osm_items[0].is_demo is False
    assert osm_items[0].verification_status == "unverified"
    assert osm_items[0].source_type == "openstreetmap_public"


def test_company_auto_quarantine_and_explicit_verification_workflow(client, db_session, admin_auth_headers):
    # 1. Creating a company with .example.com auto-quarantines it as demo_fixture
    demo_resp = client.post(
        "/api/v1/companies",
        json={
            "name": "Example Corp Demo",
            "website": "https://examplecorp.example.com",
            "city": "Siliguri",
            "public_email": "info@examplecorp.example.com",
            "is_demo": False,  # Even if caller tries False, .example.com must be quarantined
        },
        headers=admin_auth_headers,
    )
    assert demo_resp.status_code == 201
    demo_company = demo_resp.json()
    assert demo_company["is_demo"] is True
    assert demo_company["verification_status"] == "demo_fixture"

    # 2. Attempting to mark a demo fixture as 'verified' is forbidden (HTTP 400)
    bad_verify = client.post(
        f"/api/v1/companies/{demo_company['id']}/verify",
        json={"verification_status": "verified", "verification_method": "manual_review"},
        headers=admin_auth_headers,
    )
    assert bad_verify.status_code == 400

    # 3. Creating a real company starts as unverified, then can be explicitly verified with audit trail
    real_resp = client.post(
        "/api/v1/companies",
        json={
            "name": "Eastern Cloud Systems Pvt Ltd",
            "website": "https://easterncloud.in",
            "city": "Patna",
            "state": "Bihar",
            "industry": "Software Development",
            "public_email": "contact@easterncloud.in",
            "is_demo": False,
        },
        headers=admin_auth_headers,
    )
    assert real_resp.status_code == 201
    real_company = real_resp.json()
    assert real_company["is_demo"] is False
    assert real_company["verification_status"] == "unverified"

    verify_resp = client.post(
        f"/api/v1/companies/{real_company['id']}/verify",
        json={
            "verification_status": "verified",
            "verification_method": "mca_and_website_review",
            "laptop_count_verified": 12,
            "laptop_count_evidence": "Confirmed via careers page and onboarding policy",
            "source_url": "https://easterncloud.in/careers",
            "notes": "Verified by BDR analyst",
        },
        headers=admin_auth_headers,
    )
    assert verify_resp.status_code == 200
    verified = verify_resp.json()
    assert verified["verification_status"] == "verified"
    assert verified["verification_method"] == "mca_and_website_review"
    assert verified["laptop_count_verified"] == 12
    assert verified["has_verified_5_plus_laptops"] is True

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "verify_company_record", AuditLog.entity_id == str(real_company["id"]))
        .first()
    )
    assert audit is not None


def test_research_report_flags_missing_info_and_never_fabricates_facts(client, admin_auth_headers, monkeypatch):
    # Prevent live outbound HTTP during unit test
    async def _no_fetch(url: str):
        return None

    import app.services.research_service as rs
    monkeypatch.setattr(rs, "fetch_website_content_safely", _no_fetch)

    # Sparse real company with many missing fields
    comp_resp = client.post(
        "/api/v1/companies",
        json={
            "name": "Sparse Regional Tech",
            "city": "Bhagalpur",
            "industry": "IT Services",
            "is_demo": False,
        },
        headers=admin_auth_headers,
    )
    assert comp_resp.status_code == 201
    cid = comp_resp.json()["id"]

    rep_resp = client.post(f"/api/v1/research/company/{cid}", headers=admin_auth_headers)
    assert rep_resp.status_code == 200
    report = rep_resp.json()

    # Must NOT invent employee counts like "5+-25+" or fake security breaches
    assert "5+-25+" not in report["summary"]
    assert "cyberattack" not in report["summary"].lower()
    assert "breach" not in report["summary"].lower()
    assert "Unknown" in report["summary"] or "unverified" in report["summary"].lower()
    assert "Unknown" in report["relevant_decision_maker_role"]

    # Must explicitly list missing information and honest low confidence
    assert report["missing_information"]
    assert "website" in report["missing_information"].lower()
    assert "email" in report["missing_information"].lower()
    assert "laptop" in report["missing_information"].lower()
    assert report["confidence_level"] == 0.0

    # Qualification must include honest heuristic note and keep employee count separate from laptop count
    qual_resp = client.post(f"/api/v1/qualification/company/{cid}", headers=admin_auth_headers)
    assert qual_resp.status_code == 200
    qual = qual_resp.json()
    assert qual["has_verified_5_plus_laptops"] is False
    assert "heuristic prioritization aid" in qual["distinction_note"].lower()
    assert "unverified" in qual["distinction_note"].lower()
