import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base
from app.api.deps import get_db
from app.main import app
from app.services.auth_service import create_user
from app.schemas.auth import UserCreate
from app.models.company import Company
from app.models.user import User


@pytest.fixture(scope="function")
def enable_mocked_live_send(monkeypatch):
    """Explicit fixture for designated integration test harnesses with mocked HTTP providers."""
    monkeypatch.setattr(settings, "LIVE_SEND_ENABLED", True)


@pytest.fixture(autouse=True)
def configure_test_environment(monkeypatch):
    """Configures deterministic test environment flags."""
    monkeypatch.setattr(settings, "ENFORCE_TRAI_CURFEW", False)
    # Clear Redis discovery cache keys to prevent cross-test leakage
    try:
        from app.services.job_service import get_redis_client
        r = get_redis_client()
        if r:
            for k in r.scan_iter("discovery:*"):
                r.delete(k)
    except Exception:
        pass


@pytest.fixture(scope="function")
def db_session():
    # Ensure isolated rate-limit sliding window per test (both Redis and in-memory fallback)
    from app.services import job_service
    job_service.reset_rate_limit("email_dispatch")
    job_service.reset_rate_limit("whatsapp_dispatch")
    # Use StaticPool so all connections share the exact same in-memory SQLite database instance
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db(db_session):
    """Alias for db_session fixture."""
    return db_session


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_sales_user(db_session):
    user = db_session.query(User).filter(User.email == "sales@acttrident.ai").first()
    if not user:
        user = create_user(db_session, UserCreate(
            email="sales@acttrident.ai",
            password="SalesPassword2026!",
            full_name="ActTrident BD Specialist",
            role="sales_rep"
        ), role="sales_rep")
    return user


@pytest.fixture(scope="function")
def test_company(db_session):
    company = Company(
        name="Test Kanchenjunga Tech",
        city="Siliguri",
        state="West Bengal",
        industry="Software Development",
        public_email="contact@kanchenjunga.example.com",
        laptop_count_verified=8,
        laptop_count_evidence="8 verified Dell Latitude laptops",
        has_verified_5_plus_laptops=True,
        is_demo=False
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture(scope="function")
def auth_headers(client, db_session):
    user_in = UserCreate(
        email="test_sales@acttrident.ai",
        password="ValidPassword123!",
        full_name="Test Sales Specialist",
        role="sales_rep"
    )
    user = create_user(db_session, user_in, role="sales_rep")
    
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": "test_sales@acttrident.ai", "password": "ValidPassword123!"}
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def admin_auth_headers(client, db_session):
    admin_in = UserCreate(
        email="super_admin@acttrident.ai",
        password="AdminPassword123!",
        full_name="Super Admin",
        role="admin"
    )
    admin = create_user(db_session, admin_in, role="admin")
    
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": "super_admin@acttrident.ai", "password": "AdminPassword123!"}
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
