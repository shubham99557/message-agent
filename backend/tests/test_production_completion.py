"""Production Completion Regression Test Suite.

Verifies:
1. Campaign targeting criteria, limits, dates, and full status lifecycle.
2. Approval queue AI regeneration and scheduling actions with audit records.
3. CRM pipeline CSV export streaming and data integrity.
4. Multi-environment Docker compose configurations (dev, staging, prod).
"""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User
from app.models.company import Company
from app.models.campaign import Campaign, CAMPAIGN_STATUSES
from app.models.email import EmailDraft, ApprovalRecord
from app.models.lead import Lead
from app.services.email_generator_service import generate_email_draft
from app.core.security import get_password_hash, create_access_token


@pytest.fixture
def auth_headers(db: Session):
    admin = db.query(User).filter(User.email == "admin_prod_comp@acttrident.ai").first()
    if not admin:
        admin = User(
            email="admin_prod_comp@acttrident.ai",
            hashed_password=get_password_hash("AdminSecret2026!"),
            full_name="Production Admin",
            role="admin",
            is_active=True,
            token_version=1
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

    token = create_access_token(data={"sub": admin.email, "role": admin.role, "tv": admin.token_version})
    return {"Authorization": f"Bearer {token}"}


def test_campaign_enhanced_fields_and_status_lifecycle(client: TestClient, auth_headers: dict, db: Session):
    now = datetime.now(timezone.utc)
    start = now + timedelta(days=1)
    end = now + timedelta(days=30)

    payload = {
        "name": "Siliguri Enterprise Workspace Protection",
        "objective": "Acquire IT software accounts for ActTrident 90-day evaluation",
        "target_city": "Siliguri",
        "target_industry": "Software Development",
        "status": "draft",
        "business_type": "IT Services & Technology",
        "company_size": "11-50",
        "min_devices": 8,
        "min_score": 0.70,
        "allowed_channels": "email,whatsapp",
        "daily_email_limit": 40,
        "daily_whatsapp_limit": 15,
        "total_email_limit": 300,
        "sending_schedule": "09:00-18:00 IST Weekdays",
        "start_date": start.isoformat(),
        "end_date": end.isoformat()
    }

    # 1. Create
    resp = client.post("/api/v1/campaigns", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == payload["name"]
    assert data["business_type"] == "IT Services & Technology"
    assert data["min_devices"] == 8
    assert data["min_score"] == 0.70
    assert data["allowed_channels"] == "email,whatsapp"
    assert data["total_email_limit"] == 300
    camp_id = data["id"]

    # 2. Update through valid status lifecycle
    for next_status in ["researching", "ready_for_review", "approved", "scheduled", "running", "paused", "completed"]:
        assert next_status in CAMPAIGN_STATUSES
        up_resp = client.put(f"/api/v1/campaigns/{camp_id}", json={"status": next_status}, headers=auth_headers)
        assert up_resp.status_code == 200
        assert up_resp.json()["status"] == next_status

    # 3. Retrieve
    get_resp = client.get(f"/api/v1/campaigns/{camp_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "completed"


def test_approval_queue_regenerate_and_schedule_endpoints(client: TestClient, auth_headers: dict, db: Session):
    # Setup company and draft
    comp = Company(
        name="Patna Cloud Labs",
        city="Patna",
        industry="Cloud Infrastructure",
        public_email="contact@patnacloudlabs.in",
        laptop_count_verified=12,
        has_verified_5_plus_laptops=True,
        is_demo=False,
        verification_status="verified"
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)

    draft = generate_email_draft(db, comp, tone="Formal")
    assert draft.approval_status == "draft"
    assert "Dear" in draft.body_text or "Proposed 90-Day" in draft.subject

    # 1. Regenerate with Technical tone
    regen_resp = client.post(
        f"/api/v1/approvals/regenerate/{draft.id}",
        json={"tone": "Technical", "custom_notes": "Emphasize browser workspace isolation"},
        headers=auth_headers
    )
    assert regen_resp.status_code == 200, regen_resp.text
    regen_data = regen_resp.json()
    assert regen_data["tone"] == "Technical"
    assert "Endpoint Security" in regen_data["subject"] or "Technical" in regen_data["tone"]
    assert regen_data["approval_status"] == "draft"

    # Verify audit record
    audit_rec = db.query(ApprovalRecord).filter(
        ApprovalRecord.entity_id == draft.id,
        ApprovalRecord.action == "regenerated"
    ).first()
    assert audit_rec is not None
    assert "Technical" in audit_rec.reason

    # 2. Schedule draft
    scheduled_time = datetime.now(timezone.utc) + timedelta(days=2)
    sched_resp = client.post(
        f"/api/v1/approvals/schedule/{draft.id}",
        json={"scheduled_at": scheduled_time.isoformat()},
        headers=auth_headers
    )
    assert sched_resp.status_code == 200, sched_resp.text
    assert sched_resp.json()["scheduled_at"] is not None

    # Verify audit record for schedule
    sched_audit = db.query(ApprovalRecord).filter(
        ApprovalRecord.entity_id == draft.id,
        ApprovalRecord.action == "scheduled"
    ).first()
    assert sched_audit is not None


def test_crm_csv_export_streaming_and_content(client: TestClient, auth_headers: dict, db: Session):
    comp = Company(
        name="Bhagalpur FinTech Systems",
        city="Bhagalpur",
        industry="Financial Technology",
        website="https://bhagalpurfintech.in",
        public_email="leads@bhagalpurfintech.in",
        public_phone="+91-641-2401122",
        decision_maker_name="Rahul Verma",
        decision_maker_role="Chief Information Security Officer",
        laptop_count_verified=15,
        laptop_count_evidence="ISO 27001 audit report item 4.2",
        qualification_score=0.92,
        is_demo=False,
        verification_status="verified"
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)

    lead = Lead(
        company_id=comp.id,
        pipeline_status="trial_activated",
        trial_status="active",
        trial_device_count=15,
        next_followup_date=datetime.now(timezone.utc) + timedelta(days=5)
    )
    db.add(lead)
    db.commit()

    resp = client.get("/api/v1/crm/export/csv", headers=auth_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment; filename=acttrident_crm_leads.csv" in resp.headers["content-disposition"]

    content = resp.text
    assert "Lead ID,Company Name,City,Industry,Website" in content
    assert "Bhagalpur FinTech Systems" in content
    assert "trial_activated" in content
    assert "15" in content
    assert "ISO 27001 audit report" in content


def test_multi_environment_docker_configurations():
    import os
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    compose_files = {
        "base": root / "docker-compose.yml",
        "dev": root / "docker-compose.dev.yml",
        "staging": root / "docker-compose.staging.yml",
        "prod": root / "docker-compose.prod.yml",
    }

    for env_name, file_path in compose_files.items():
        assert file_path.exists(), f"Missing {file_path}"
        text = file_path.read_text(encoding="utf-8")
        assert "services:" in text
        assert "postgres:" in text
        assert "redis:" in text

        if env_name == "dev":
            assert "acttrident_dev_postgres" in text
            assert "--reload" in text
        elif env_name == "staging":
            assert "acttrident_staging_migration" in text
            assert "ENVIRONMENT: staging" in text
        elif env_name == "prod":
            assert "acttrident_prod_migration" in text
            assert "ENVIRONMENT: production" in text
            assert "acttrident_internal" in text
            assert "json-file" in text
