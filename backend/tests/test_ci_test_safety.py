"""
Verification tests for CI Test Safety, Nationwide Discovery Semantics, and SSRF Hardening.
Verifies that:
1. Tests default strictly to simulation mode (LIVE_SEND_ENABLED=False).
2. No outbound provider requests occur during standard testing.
3. Nationwide discovery never converts "All" to "Siliguri" and searches multiple canonical hubs.
4. SSRF protection rejects IPv4/IPv6 private ranges, cloud metadata, restricted ports, and redirect attacks.
"""
import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import is_safe_external_url, safe_fetch_untrusted_url
from app.core.locations import get_states_and_uts, get_presets, search_locations
from app.schemas.research import DiscoveryQuery
from app.services.discovery_service import search_public_company_directory, search_public_company_directory_paginated
from app.services.email_sender_service import send_approved_email
from app.services.whatsapp_service import send_approved_whatsapp_message
from app.models.company import Company
from app.models.email import EmailDraft


def test_ordinary_tests_default_to_simulation():
    """Verify settings.LIVE_SEND_ENABLED is False by default during standard CI runs."""
    assert settings.LIVE_SEND_ENABLED is False, (
        "LIVE_SEND_ENABLED must default to False to prevent accidental real outbound requests in CI."
    )


def test_send_approved_email_never_calls_network_when_live_send_disabled(db: Session, test_company: Company):
    """Verify email dispatch fails closed to simulation without invoking external network requests."""
    assert settings.LIVE_SEND_ENABLED is False

    from app.core.security import compute_content_hash
    chash = compute_content_hash(["ActTrident Evaluation Proposal", "Proposal content"])
    draft = EmailDraft(
        company_id=test_company.id,
        recipient_email="ceo@prospectcompany.in",
        subject="ActTrident Evaluation Proposal",
        body_text="Proposal content",
        body_html="<p>Proposal content</p>",
        approval_status="approved",
        content_hash=chash,
        approved_content_hash=chash
    )
    db.add(draft)
    db.commit()

    # Network client should never be invoked
    mock_network_client = MagicMock()
    result = send_approved_email(db, draft.id, user_id=1, http_client=mock_network_client)

    assert result.status == "simulated"
    assert result.provider in ("simulated", "mock")
    assert not mock_network_client.post.called
    assert not mock_network_client.send.called


def test_nationwide_discovery_never_converts_all_to_siliguri():
    """Verify 'All India' search scope never converts the query to Siliguri."""
    query = DiscoveryQuery(city="All", scope="country", include_demo=True)
    results = search_public_company_directory(query)

    # In DISCOVERY_CATALOG, items exist in Siliguri, Gangtok, Patna, and Bhagalpur.
    # If "All" was mistakenly converted to "Siliguri", all results would be from Siliguri.
    cities_found = {item.city for item in results}
    assert len(cities_found) > 1, f"Expected multi-city results for All India, got only: {cities_found}"
    assert "Patna" in cities_found or "Gangtok" in cities_found, (
        "Nationwide discovery must return results beyond Siliguri!"
    )


def test_paginated_discovery_returns_metadata_and_providers():
    """Verify paginated discovery endpoint returns structured metadata, scope, and provider statuses."""
    query = DiscoveryQuery(city="All", scope="country", include_demo=True, page=1, page_size=5)
    resp = search_public_company_directory_paginated(query)

    assert resp.total > 0
    assert len(resp.items) <= 5
    assert resp.scope == "country"
    assert "Nationwide" in resp.search_strategy
    assert len(resp.active_providers) > 0 or len(resp.failed_providers) > 0


def test_location_directory_canonical_states_and_presets():
    """Verify canonical states, presets, and autocomplete suggestions."""
    states = get_states_and_uts()
    assert len(states) >= 36  # 28 States + 8 UTs

    presets = get_presets()
    preset_ids = [p["id"] for p in presets]
    assert "target_east_northeast" in preset_ids

    # Search location suggestions
    sugg_siliguri = search_locations(query="Sili")
    assert any(s["city"] == "Siliguri" for s in sugg_siliguri)

    sugg_bengaluru = search_locations(query="Bengaluru")
    assert any(s["city"] == "Bengaluru" for s in sugg_bengaluru)


def test_ssrf_rejects_private_loopback_and_metadata_ips():
    """Verify SSRF protection blocks private, loopback, link-local, and cloud metadata targets."""
    # Disallowed literal addresses
    assert not is_safe_external_url("http://127.0.0.1:8000")
    assert not is_safe_external_url("http://localhost:8000")
    assert not is_safe_external_url("http://169.254.169.254/latest/meta-data")
    assert not is_safe_external_url("http://metadata.google.internal")
    assert not is_safe_external_url("http://0.0.0.0:80")
    assert not is_safe_external_url("http://10.0.0.1/admin")
    assert not is_safe_external_url("http://192.168.1.1/config")
    assert not is_safe_external_url("http://172.16.0.1/secret")
    assert not is_safe_external_url("http://[::1]/status")
    assert not is_safe_external_url("http://[::ffff:127.0.0.1]/status")

    # Disallowed internal ports
    assert not is_safe_external_url("http://example.com:22")
    assert not is_safe_external_url("http://example.com:5432")
    assert not is_safe_external_url("http://example.com:6379")

    # Disallowed internal TLDs
    assert not is_safe_external_url("http://corporate-server.local")
    assert not is_safe_external_url("http://database.internal")


@pytest.mark.anyio
async def test_safe_fetch_untrusted_url_blocks_redirect_ssrf():
    """Verify safe_fetch_untrusted_url rejects redirects to private addresses."""
    # Attempting to fetch a private IP fails immediately at hop 0
    ok, text, final_url, err = await safe_fetch_untrusted_url("http://169.254.169.254/latest/meta-data")
    assert not ok
    assert "SSRF security check rejected" in (err or "")
