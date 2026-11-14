import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.api.deps import get_db
from app.main import app
from app.services.auth_service import create_user
from app.schemas.auth import UserCreate


@pytest.fixture(scope="function")
def db_session():
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
def auth_headers(client, db_session):
    user_in = UserCreate(
        email="test_sales@acttrident.ai",
        password="ValidPassword123!",
        full_name="Test Sales Specialist",
        role="sales_rep"
    )
    user = create_user(db_session, user_in)
    
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
    admin = create_user(db_session, admin_in)
    
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": "super_admin@acttrident.ai", "password": "AdminPassword123!"}
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
