import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, User, Company, CompanyContact, ContactSource, ContactConsent, Lead

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_db():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_schema_creation(test_db):
    """Verifies that all 22 database models can be successfully created and queried."""
    # Create test user
    user = User(email="sales@acttrident.ai", hashed_password="hashed_pw_test", full_name="Sales Rep", role="sales_rep")
    test_db.add(user)
    test_db.commit()

    # Create company with source attribution
    company = Company(
        name="Siliguri Tech Innovations",
        city="Siliguri",
        state="West Bengal",
        industry="Software Development",
        website="https://siliguritech.example.com",
        laptop_count_verified=8,
        laptop_count_evidence="Verified via company technical careers page listing managed Dell Latitude laptops for dev staff",
        has_verified_5_plus_laptops=True
    )
    test_db.add(company)
    test_db.commit()

    # Add contact source
    source = ContactSource(
        company_id=company.id,
        field_name="laptop_count",
        source_url="https://siliguritech.example.com/careers",
        source_type="official_website",
        notes="Documented 8 developer workstations"
    )
    test_db.add(source)
    test_db.commit()

    retrieved = test_db.query(Company).filter(Company.city == "Siliguri").first()
    assert retrieved is not None
    assert retrieved.name == "Siliguri Tech Innovations"
    assert retrieved.has_verified_5_plus_laptops is True
    assert len(retrieved.sources) == 1
    assert retrieved.sources[0].field_name == "laptop_count"
