import pytest
from datetime import datetime, timezone, timedelta
from app.models.service_catalogue import ServiceCatalogueItem
from app.models.company import Company
from app.models.lead import Lead, Followup
from app.models.activity import SuppressionList
from app.schemas.research import DiscoveredCompanyItem
from app.services.service_catalogue_service import seed_default_services, match_service_for_company, get_services
from app.services.verification_service import check_email_domain_mx, verify_discovered_company
from app.services.email_generator_service import generate_email_draft, build_email_content


def test_service_catalogue_seeding_and_crud(client, admin_auth_headers, auth_headers, db_session):
    """Verifies seeding and admin CRUD operations for ActTrident Service Catalogue."""
    # 1. Seeding
    seeded = seed_default_services(db_session)
    assert seeded == 3
    services = get_services(db_session)
    assert len(services) == 3
    codes = {s.service_code for s in services}
    assert "ACT-WS-01" in codes
    assert "ACT-CL-02" in codes
    assert "ACT-AU-03" in codes

    # 2. List via API
    res = client.get("/api/v1/services", headers=auth_headers)
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 3

    # 3. Create Custom Service (Admin)
    new_svc_payload = {
        "service_code": "ACT-CY-04",
        "service_name": "Zero-Trust Identity & Access Verification",
        "description": "Hardware security key enforcement and MFA posture auditing.",
        "target_business_types": ["fintech", "banking", "healthcare"],
        "common_business_problems": ["credential phishing", "unauthorized session hijacking"],
        "required_qualification_signals": {"min_score": 70},
        "approved_claims": ["Hardware token attestation", "FIDO2 WebAuthn enforcement"],
        "disallowed_claims": ["100% impenetrable security guarantee"],
        "is_active": True
    }
    create_res = client.post("/api/v1/services", json=new_svc_payload, headers=admin_auth_headers)
    assert create_res.status_code == 201
    created_id = create_res.json()["id"]

    # 4. Update Custom Service
    update_res = client.put(
        f"/api/v1/services/{created_id}",
        json={"description": "Updated zero-trust identity verification brief."},
        headers=admin_auth_headers
    )
    assert update_res.status_code == 200
    assert update_res.json()["description"] == "Updated zero-trust identity verification brief."

    # 5. Non-admin forbidden to create
    denied_res = client.post("/api/v1/services", json=new_svc_payload, headers=auth_headers)
    assert denied_res.status_code == 403


def test_intelligent_service_matching(db_session):
    """Verifies multi-dimensional rule-based matching selects correct ActTrident services."""
    seed_default_services(db_session)

    # 1. Software Engineering Company -> ACT-WS-01 (Workspace & Endpoint Isolation)
    comp_software = Company(
        name="Apex Software Labs",
        city="Siliguri",
        industry="Software Development",
        description="Full stack software engineering, React, Python and mobile application development for enterprise clients.",
        laptop_count_verified=15,
        has_verified_5_plus_laptops=True
    )
    match_sw = match_service_for_company(comp_software, db=db_session)
    assert match_sw is not None
    assert match_sw.service_code == "ACT-WS-01"
    assert "software" in match_sw.rationale.lower() or "developer" in match_sw.rationale.lower() or "workspace" in match_sw.rationale.lower()

    # 2. Cloud & DevOps Company -> ACT-CL-02 (Cloud Infrastructure & SaaS Credential Protection)
    comp_cloud = Company(
        name="Sikkim Cloud Architects",
        city="Gangtok",
        industry="Cloud Infrastructure & DevOps",
        description="AWS and GCP cloud consulting, Docker containerization, Kubernetes cluster management, and database hosting.",
        has_verified_5_plus_laptops=True
    )
    match_cl = match_service_for_company(comp_cloud, db=db_session)
    assert match_cl is not None
    assert match_cl.service_code == "ACT-CL-02"
    assert "cloud" in match_cl.recommended_outreach_angle.lower() or "credential" in match_cl.recommended_outreach_angle.lower()

    # 3. B2B Staffing & Sales Agency -> ACT-AU-03 (B2B Outreach & Sales Operations Automation)
    comp_b2b = Company(
        name="Apex Talent Solutions & B2B Consulting",
        city="Patna",
        industry="Business Consulting & Staffing",
        description="B2B recruitment, executive staffing, digital marketing, and business sales solutions for commercial enterprises.",
        has_verified_5_plus_laptops=False
    )
    match_b2b = match_service_for_company(comp_b2b, db=db_session)
    assert match_b2b is not None
    assert match_b2b.service_code == "ACT-AU-03"
    assert "outreach" in match_b2b.recommended_outreach_angle.lower() or "b2b" in match_b2b.recommended_outreach_angle.lower()


@pytest.mark.anyio
async def test_granular_contact_verification_and_website_classification():
    """Verifies DNS MX check, contact status granularity, and website authenticity classification."""
    # 1. DNS MX test on real deliverable domain
    mx_valid = check_email_domain_mx("test@google.com")
    assert mx_valid is True

    # 2. DNS MX test on guaranteed non-existent domain
    mx_invalid = check_email_domain_mx("test@nonexistentdomainxyz123456789.org")
    assert mx_invalid is False

    # 3. Discovered item with valid deliverable email
    item = DiscoveredCompanyItem(
        name="Siliguri Tech Innovations",
        city="Siliguri",
        source_url="https://osm.test/node/101",
        public_email="info@google.com",  # real domain for MX resolution
        public_phone="+91-9832012345",
        industry="Information Technology"
    )
    verified_item = await verify_discovered_company(item)
    assert verified_item.email_verification_status in ("domain_checked", "syntax_valid", "independently_verified", "source_confirmed")
    assert verified_item.phone_verification_status == "format_valid"
    assert verified_item.website_classification == "unavailable"

    # 4. Discovered item with invalid syntax email
    item_bad_email = DiscoveredCompanyItem(
        name="Faulty Lead",
        city="Siliguri",
        source_url="https://osm.test/node/102",
        public_email="bad_email_not_valid.png",
        industry="Software"
    )
    verified_bad = await verify_discovered_company(item_bad_email)
    assert verified_bad.email_verification_status == "invalid"


def test_followup_scheduling_and_task_lifecycle(client, auth_headers, test_company, db_session):
    """Verifies multi-touch follow-up scheduling, listing, and status updates."""
    # Create CRM lead
    lead = Lead(
        company_id=test_company.id,
        pipeline_status="contacted"
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    # 1. Schedule a follow-up via API
    scheduled_iso = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    create_payload = {
        "scheduled_date": scheduled_iso,
        "suggested_channel": "email",
        "reason": "Touch 2: Technical architecture follow-up",
        "notes": "Follow up regarding developer endpoint isolation"
    }
    create_res = client.post(f"/api/v1/crm/leads/{lead.id}/followups", json=create_payload, headers=auth_headers)
    assert create_res.status_code == 201
    fu_id = create_res.json()["id"]

    # 2. List followups
    list_res = client.get("/api/v1/crm/followups", headers=auth_headers)
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] >= 1
    assert any(f["id"] == fu_id for f in data["items"])

    # 3. Update followup status to completed
    patch_res = client.patch(
        f"/api/v1/crm/followups/{fu_id}",
        json={"status": "completed", "notes": "Completed call; prospect requested follow-up proposal"},
        headers=auth_headers
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "completed"
    assert patch_res.json()["completed_at"] is not None


def test_suppression_list_management_and_outreach_blocking(client, admin_auth_headers, auth_headers, test_company, db_session):
    """Verifies adding suppression entries and fail-closed blocking of outreach generation."""
    suppressed_email = "privacy-optout@targetfirm.in"
    test_company.public_email = suppressed_email
    db_session.commit()

    # 1. Add email to suppression list via Settings API
    supp_res = client.post(
        "/api/v1/settings/suppression-list",
        json={"identifier": suppressed_email, "channel": "all", "reason": "user_opt_out"},
        headers=admin_auth_headers
    )
    assert supp_res.status_code == 201
    supp_id = supp_res.json()["id"]

    # 2. Attempt outreach generation for company with suppressed email
    draft = generate_email_draft(
        db=db_session,
        company=test_company,
        tone="Professional",
        draft_type="initial_email"
    )
    assert draft.approval_status == "rejected"
    assert "suppression" in draft.rejection_reason.lower()

    # 3. Remove from suppression
    del_res = client.delete(f"/api/v1/settings/suppression-list/{supp_id}", headers=admin_auth_headers)
    assert del_res.status_code == 204


def test_outreach_generation_styles_and_channels(db_session, test_company):
    """Verifies generation across multiple draft types and styles adhering to strict claims boundaries."""
    seed_default_services(db_session)

    # 1. WhatsApp Draft (Concise & Conversational)
    s_wa, b_wa_text, _ = build_email_content(
        company=test_company,
        contact=None,
        tone="Concise",
        draft_type="whatsapp_draft",
        target_service_name="Secure Workspace & Endpoint Isolation"
    )
    assert "ActTrident" in b_wa_text
    assert "5-minute chat" in b_wa_text or "overview" in b_wa_text

    # 2. LinkedIn Message (Concise connection note)
    s_li, b_li_text, _ = build_email_content(
        company=test_company,
        contact=None,
        tone="Professional",
        draft_type="linkedin_message",
        target_service_name="Secure Workspace & Endpoint Isolation"
    )
    assert "Connecting re:" in s_li
    assert test_company.name in b_li_text

    # 3. Technical Style Email
    s_tech, b_tech_text, _ = build_email_content(
        company=test_company,
        contact=None,
        tone="Technical",
        draft_type="initial_email",
        target_service_name="Secure Workspace & Endpoint Isolation"
    )
    assert "architecture" in s_tech.lower() or "endpoint" in s_tech.lower()
    assert "runtime workspace protection" in b_tech_text.lower() or "credential" in b_tech_text.lower()

    # 4. Verify Claims Guardrails: Disallowed exaggerated claims must not appear
    for text in [b_wa_text, b_li_text, b_tech_text]:
        assert "100% hack-proof" not in text
        assert "military-grade impenetrable" not in text
        assert "replaces all firewalls" not in text
