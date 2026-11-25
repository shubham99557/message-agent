import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.user import User
from app.models.company import Company
from app.models.campaign import Campaign
from app.models.email import EmailDraft
from app.models.lead import Lead
from app.core.security import get_password_hash, create_access_token


@pytest.fixture
def analyst_token(db_session: Session) -> str:
    user = User(
        email="analyst@acttrident.internal",
        hashed_password=get_password_hash("AnalystSecure2026!"),
        full_name="Market Intelligence Analyst",
        role="analyst",
        is_active=True,
        token_version=1
    )
    db_session.add(user)
    db_session.commit()
    return create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": user.id, "tv": 1}
    )


@pytest.fixture
def admin_token(db_session: Session) -> str:
    admin = User(
        email="superadmin@acttrident.internal",
        hashed_password=get_password_hash("AdminPass2026!"),
        full_name="Platform SuperAdmin",
        role="admin",
        is_active=True,
        token_version=1
    )
    db_session.add(admin)
    db_session.commit()
    return create_access_token(
        data={"sub": admin.email, "role": admin.role, "user_id": admin.id, "tv": 1}
    )


def test_admin_can_provision_analyst_user(client: TestClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "email": "new.analyst@acttrident.internal",
            "full_name": "Field Research Analyst",
            "password": "Password123!",
            "role": "analyst"
        }
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "analyst"
    assert data["email"] == "new.analyst@acttrident.internal"


def test_analyst_can_access_read_only_endpoints(
    client: TestClient,
    analyst_token: str,
    db_session: Session
):
    headers = {"Authorization": f"Bearer {analyst_token}"}

    # Seed sample company & lead
    comp = Company(
        name="Analyst Test Corp",
        city="Siliguri",
        industry="Software Development",
        laptop_count_verified=10,
        laptop_count_evidence="MCA verified",
        is_demo=False
    )
    db_session.add(comp)
    db_session.commit()

    lead = Lead(company_id=comp.id, pipeline_status="new")
    db_session.add(lead)
    db_session.commit()

    # 1. Analytics endpoints
    r1 = client.get("/api/v1/analytics/dashboard", headers=headers)
    assert r1.status_code == 200

    r2 = client.get("/api/v1/analytics/cities", headers=headers)
    assert r2.status_code == 200

    r3 = client.get("/api/v1/analytics/campaigns", headers=headers)
    assert r3.status_code == 200

    r4 = client.get("/api/v1/analytics/daily-digest", headers=headers)
    assert r4.status_code == 200

    # 2. Campaigns read
    r5 = client.get("/api/v1/campaigns", headers=headers)
    assert r5.status_code == 200

    # 3. Companies read
    r6 = client.get("/api/v1/companies", headers=headers)
    assert r6.status_code == 200
    assert r6.json()["total"] >= 1

    # 4. Approvals queue read
    r7 = client.get("/api/v1/approvals/queue", headers=headers)
    assert r7.status_code == 200

    # 5. CRM read & CSV export
    r8 = client.get("/api/v1/crm/leads", headers=headers)
    assert r8.status_code == 200

    r9 = client.get("/api/v1/crm/export/csv", headers=headers)
    assert r9.status_code == 200
    assert "text/csv" in r9.headers["content-type"]

    # 6. Jobs health & history read
    r10 = client.get("/api/v1/jobs/health", headers=headers)
    assert r10.status_code == 200

    r11 = client.get("/api/v1/jobs/history", headers=headers)
    assert r11.status_code == 200


def test_analyst_cannot_mutate_data(
    client: TestClient,
    analyst_token: str,
    db_session: Session
):
    headers = {"Authorization": f"Bearer {analyst_token}"}

    # 1. Cannot create campaign
    r1 = client.post(
        "/api/v1/campaigns",
        headers=headers,
        json={"name": "Analyst Campaign", "target_city": "Siliguri"}
    )
    assert r1.status_code == 403

    # 2. Cannot create company
    r2 = client.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "Forbidden Company", "city": "Patna"}
    )
    assert r2.status_code == 403

    # Seed company for further mutations
    comp = Company(name="Test Target", city="Gangtok", is_demo=False)
    db_session.add(comp)
    db_session.commit()

    lead = Lead(company_id=comp.id, pipeline_status="new")
    db_session.add(lead)
    db_session.commit()

    # 3. Cannot update CRM pipeline status
    r3 = client.patch(
        f"/api/v1/crm/leads/{lead.id}/status",
        headers=headers,
        json={"status": "contacted", "notes": "analyst tried to change"}
    )
    assert r3.status_code == 403

    # 4. Cannot schedule followup
    r4 = client.post(
        f"/api/v1/crm/leads/{lead.id}/followups",
        headers=headers,
        json={"due_date": "2026-12-01T10:00:00Z", "channel": "email"}
    )
    assert r4.status_code == 403

    # 5. Cannot activate evaluation trial
    r5 = client.post(
        f"/api/v1/crm/leads/{lead.id}/trials",
        headers=headers,
        json={"devices_count": 10}
    )
    assert r5.status_code == 403

    # 6. Cannot trigger background tasks
    r6 = client.post(
        "/api/v1/jobs/trigger",
        headers=headers,
        json={"category": "nightly_discovery"}
    )
    assert r6.status_code == 403

    # 7. Cannot toggle kill switch
    r7 = client.post(
        "/api/v1/settings/kill-switch",
        headers=headers,
        json={"active": True, "reason": "Analyst halt"}
    )
    assert r7.status_code == 403
