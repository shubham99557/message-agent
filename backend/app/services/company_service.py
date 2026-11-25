import csv
import io
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.company import Company, CompanyContact, ContactSource
from app.models.consent import ContactConsent
from app.models.lead import Lead
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyVerifyRequest, ContactSourceCreate, CSVImportSummary
from app.integrations.discovery_adapters import is_demo_domain


def normalize_domain(url_or_domain: Optional[str]) -> Optional[str]:
    if not url_or_domain:
        return None
    val = url_or_domain.lower().strip()
    val = val.replace("https://", "").replace("http://", "").replace("www.", "")
    val = val.split("/")[0]
    return val


def find_duplicate_company(
    db: Session,
    name: str,
    website: Optional[str] = None,
    email: Optional[str] = None,
    source_url: Optional[str] = None,
) -> Optional[Company]:
    if source_url:
        from app.models.company import ContactSource
        matched_source = db.query(ContactSource).filter(ContactSource.source_url == source_url.strip()).first()
        if matched_source and matched_source.company_id:
            comp = db.query(Company).filter(Company.id == matched_source.company_id).first()
            if comp:
                return comp

    query = db.query(Company)
    conditions = []
    
    if name:
        conditions.append(Company.name.ilike(name.strip()))
    
    if website:
        domain = normalize_domain(website)
        if domain:
            conditions.append(Company.website.ilike(f"%{domain}%"))
            
    if email:
        conditions.append(Company.public_email.ilike(email.strip()))

    if conditions:
        return query.filter(or_(*conditions)).first()
    return None


def create_company(db: Session, comp_in: CompanyCreate, user_id: Optional[int] = None) -> Company:
    # Validate verified laptops: strictly track states VERIFIED, CLAIMED, UNKNOWN
    has_5_laptops = bool(comp_in.laptop_count_verified and comp_in.laptop_count_verified >= 5 and comp_in.laptop_count_evidence)
    if has_5_laptops:
        fleet_status = "VERIFIED"
    elif comp_in.laptop_count_verified and comp_in.laptop_count_verified >= 5:
        fleet_status = "CLAIMED"
    else:
        fleet_status = "UNKNOWN"

    # Quarantine .example.com / demo fixtures so fictional domains are never marked as verified real businesses
    auto_demo = bool(
        comp_in.is_demo
        or is_demo_domain(comp_in.website)
        or is_demo_domain(comp_in.public_email)
    )
    verif_status = "demo_fixture" if auto_demo else "unverified"
    verif_method = "demo_fixture" if auto_demo else ("official_website" if comp_in.website else "manual_entry")

    company = Company(
        name=comp_in.name.strip(),
        website=comp_in.website.strip() if comp_in.website else None,
        industry=comp_in.industry.strip() if comp_in.industry else None,
        description=comp_in.description,
        city=comp_in.city.strip(),
        state=comp_in.state.strip() if comp_in.state else None,
        country=comp_in.country or "India",
        employee_count_min=comp_in.employee_count_min,
        employee_count_max=comp_in.employee_count_max,
        employee_size_evidence=comp_in.employee_size_evidence,
        laptop_count_verified=comp_in.laptop_count_verified,
        laptop_count_evidence=comp_in.laptop_count_evidence,
        laptop_fleet_status=fleet_status,
        has_verified_5_plus_laptops=has_5_laptops,
        public_email=comp_in.public_email.strip() if comp_in.public_email else None,
        public_phone=comp_in.public_phone.strip() if comp_in.public_phone else None,
        public_whatsapp=comp_in.public_whatsapp.strip() if comp_in.public_whatsapp else None,
        linkedin_url=comp_in.linkedin_url.strip() if comp_in.linkedin_url else None,
        decision_maker_name=comp_in.decision_maker_name,
        decision_maker_role=comp_in.decision_maker_role,
        decision_maker_email=comp_in.decision_maker_email,
        decision_maker_linkedin=comp_in.decision_maker_linkedin,
        is_demo=auto_demo,
        verification_status=verif_status,
        verification_method=verif_method,
        created_by_id=user_id,
        date_last_verified=datetime.now(timezone.utc)
    )
    db.add(company)
    db.flush()

    # Record source attribution if provided
    source_url = comp_in.source_url or comp_in.website or "Direct Entry"
    if comp_in.public_email:
        source_email = ContactSource(
            company_id=company.id,
            field_name="public_email",
            source_url=source_url,
            source_type="official_website" if comp_in.website else "user_entry",
            extracted_text=comp_in.source_notes or "Collected during company profiling"
        )
        db.add(source_email)

    if comp_in.public_phone:
        source_phone = ContactSource(
            company_id=company.id,
            field_name="public_phone",
            source_url=source_url,
            source_type="official_website" if comp_in.website else "user_entry",
            extracted_text=comp_in.source_notes or "Public business telephone"
        )
        db.add(source_phone)

    if comp_in.laptop_count_evidence:
        source_laptop = ContactSource(
            company_id=company.id,
            field_name="laptop_count",
            source_url=source_url,
            source_type="official_website" if comp_in.website else "user_entry",
            extracted_text=comp_in.laptop_count_evidence
        )
        db.add(source_laptop)

    # Initialize associated CRM Lead record
    lead = Lead(
        company_id=company.id,
        pipeline_status="new",
        notes="Discovered and added to system"
    )
    db.add(lead)

    db.commit()
    db.refresh(company)
    return company


def list_companies(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    city: Optional[str] = None,
    state: Optional[str] = None,
    industry: Optional[str] = None,
    qualification_status: Optional[str] = None,
    has_laptops: Optional[bool] = None,
    search: Optional[str] = None,
    is_demo: Optional[bool] = None,
    sort_by: str = "newest_first",
) -> Tuple[List[Company], int]:
    query = db.query(Company)

    if is_demo is not None:
        query = query.filter(Company.is_demo == is_demo)
    if city:
        query = query.filter(Company.city.ilike(f"%{city.strip()}%"))
    if state:
        query = query.filter(Company.state.ilike(f"%{state.strip()}%"))
    if industry and industry.lower() != "all":
        query = query.filter(Company.industry.ilike(f"%{industry.strip()}%"))
    if qualification_status and qualification_status.lower() != "all":
        query = query.filter(Company.qualification_status == qualification_status)
    if has_laptops is not None:
        query = query.filter(Company.has_verified_5_plus_laptops == has_laptops)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(or_(
            Company.name.ilike(s),
            Company.website.ilike(s),
            Company.public_email.ilike(s),
            Company.decision_maker_name.ilike(s)
        ))

    total = query.count()
    sort_key = (sort_by or "newest_first").strip().lower()
    if sort_key == "oldest_first":
        order_clauses = (Company.created_at.asc(), Company.id.asc())
    elif sort_key == "qualification_desc":
        order_clauses = (Company.qualification_score.desc(), Company.created_at.desc(), Company.id.desc())
    elif sort_key == "name_asc":
        order_clauses = (Company.name.asc(), Company.id.desc())
    else:
        order_clauses = (Company.created_at.desc(), Company.id.desc())
    companies = query.order_by(*order_clauses).offset(skip).limit(limit).all()
    return companies, total


def get_company(db: Session, company_id: int) -> Optional[Company]:
    return db.query(Company).filter(Company.id == company_id).first()


def update_company(db: Session, company_id: int, comp_update: CompanyUpdate) -> Optional[Company]:
    company = get_company(db, company_id)
    if not company:
        return None

    update_data = comp_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    # Recalculate laptop verification flag and fleet status if updated
    if "laptop_count_verified" in update_data or "laptop_count_evidence" in update_data:
        has_5 = bool(
            company.laptop_count_verified and
            company.laptop_count_verified >= 5 and
            company.laptop_count_evidence
        )
        company.has_verified_5_plus_laptops = has_5
        if has_5:
            company.laptop_fleet_status = "VERIFIED"
        elif company.laptop_count_verified and company.laptop_count_verified >= 5:
            company.laptop_fleet_status = "CLAIMED"
        else:
            company.laptop_fleet_status = "UNKNOWN"

    company.date_last_verified = datetime.now(timezone.utc)
    db.commit()
    db.refresh(company)
    return company


def verify_company_record(
    db: Session,
    company_id: int,
    verify_in: CompanyVerifyRequest,
) -> Optional[Company]:
    """
    Allows sales/admin users to manually verify or correct a company's evidence and contacts.
    Strictly forbids marking .example.com demo fixtures as verified real companies.
    """
    allowed_statuses = {"verified", "unverified", "inferred", "unknown"}
    if verify_in.verification_status not in allowed_statuses:
        raise ValueError(f"Invalid verification_status '{verify_in.verification_status}'. Allowed: {sorted(allowed_statuses)}")

    company = get_company(db, company_id)
    if not company:
        return None

    # Never allow marking fictional .example.com fixtures as verified real companies
    if verify_in.verification_status == "verified" and (
        company.is_demo or is_demo_domain(company.website) or is_demo_domain(company.public_email)
    ):
        raise ValueError("Demo fixtures or .example.com records cannot be marked as verified genuine companies.")

    if verify_in.public_email is not None:
        company.public_email = verify_in.public_email.strip()
    if verify_in.public_phone is not None:
        company.public_phone = verify_in.public_phone.strip()
    if verify_in.decision_maker_name is not None:
        company.decision_maker_name = verify_in.decision_maker_name.strip()
    if verify_in.decision_maker_role is not None:
        company.decision_maker_role = verify_in.decision_maker_role.strip()
    if verify_in.laptop_count_verified is not None:
        company.laptop_count_verified = verify_in.laptop_count_verified
    if verify_in.laptop_count_evidence is not None:
        company.laptop_count_evidence = verify_in.laptop_count_evidence.strip()

    company.has_verified_5_plus_laptops = bool(
        company.laptop_count_verified and company.laptop_count_verified >= 5 and company.laptop_count_evidence
    )
    company.verification_status = verify_in.verification_status
    company.verification_method = verify_in.verification_method
    company.date_last_verified = datetime.now(timezone.utc)

    for src in company.sources:
        src.verification_status = verify_in.verification_status
        src.verification_method = verify_in.verification_method

    db.commit()
    db.refresh(company)
    return company


def add_contact_source(db: Session, source_in: ContactSourceCreate) -> ContactSource:
    source = ContactSource(
        company_id=source_in.company_id,
        field_name=source_in.field_name,
        source_url=source_in.source_url,
        source_type=source_in.source_type,
        extracted_text=source_in.notes,
        retrieved_at=datetime.now(timezone.utc)
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def import_companies_from_csv(db: Session, csv_content: str, user_id: Optional[int] = None) -> CSVImportSummary:
    reader = csv.DictReader(io.StringIO(csv_content))
    created = 0
    updated = 0
    skipped = 0
    errors = []
    row_num = 1

    for row in reader:
        row_num += 1
        name = row.get("name") or row.get("Company Name") or row.get("Company")
        if not name:
            errors.append(f"Row {row_num}: Missing company name")
            continue

        city = row.get("city") or row.get("City") or "Siliguri"
        website = row.get("website") or row.get("Official Website") or row.get("Website")
        email = row.get("email") or row.get("public_email") or row.get("Email")
        phone = row.get("phone") or row.get("public_phone") or row.get("Phone")
        industry = row.get("industry") or row.get("Industry")
        desc = row.get("description") or row.get("Description")

        # Employee counts
        emp_min = None
        emp_max = None
        try:
            if row.get("employee_count_min"):
                emp_min = int(row.get("employee_count_min"))
            if row.get("employee_count_max"):
                emp_max = int(row.get("employee_count_max"))
        except ValueError:
            pass

        # Managed laptop count (requires explicit evidence)
        laptop_count = None
        laptop_evidence = row.get("laptop_count_evidence") or row.get("Laptop Evidence")
        try:
            raw_lap = row.get("laptop_count_verified") or row.get("Verified Laptops")
            if raw_lap:
                laptop_count = int(raw_lap)
        except ValueError:
            pass

        existing = find_duplicate_company(db, name=name, website=website, email=email)
        if existing:
            # Update fields if new data provided
            if not existing.website and website:
                existing.website = website
            if not existing.public_email and email:
                existing.public_email = email
            if not existing.public_phone and phone:
                existing.public_phone = phone
            db.commit()
            updated += 1
            skipped += 1
        else:
            comp_create = CompanyCreate(
                name=name,
                city=city,
                state=row.get("state") or row.get("State"),
                country="India",
                website=website,
                industry=industry,
                description=desc,
                public_email=email,
                public_phone=phone,
                public_whatsapp=row.get("whatsapp") or row.get("WhatsApp"),
                employee_count_min=emp_min,
                employee_count_max=emp_max,
                employee_size_evidence=row.get("employee_size_evidence"),
                laptop_count_verified=laptop_count,
                laptop_count_evidence=laptop_evidence,
                source_url=website or "CSV Upload",
                is_demo=False
            )
            create_company(db, comp_create, user_id=user_id)
            created += 1

    return CSVImportSummary(
        total_processed=row_num - 1,
        created_count=created,
        updated_count=updated,
        duplicate_skipped_count=skipped,
        errors=errors
    )
