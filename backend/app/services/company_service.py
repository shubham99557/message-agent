import csv
import io
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.company import Company, CompanyContact, ContactSource
from app.models.consent import ContactConsent
from app.models.lead import Lead
from app.schemas.company import CompanyCreate, CompanyUpdate, ContactSourceCreate, CSVImportSummary


def normalize_domain(url_or_domain: Optional[str]) -> Optional[str]:
    if not url_or_domain:
        return None
    val = url_or_domain.lower().strip()
    val = val.replace("https://", "").replace("http://", "").replace("www.", "")
    val = val.split("/")[0]
    return val


def find_duplicate_company(db: Session, name: str, website: Optional[str] = None, email: Optional[str] = None) -> Optional[Company]:
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


def create_company(db: Session, comp_in: CompanyCreate) -> Company:
    # Validate verified laptops: never label as having 5+ laptops without evidence
    has_5_laptops = bool(comp_in.laptop_count_verified and comp_in.laptop_count_verified >= 5 and comp_in.laptop_count_evidence)

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
        has_verified_5_plus_laptops=has_5_laptops,
        public_email=comp_in.public_email.strip() if comp_in.public_email else None,
        public_phone=comp_in.public_phone.strip() if comp_in.public_phone else None,
        public_whatsapp=comp_in.public_whatsapp.strip() if comp_in.public_whatsapp else None,
        linkedin_url=comp_in.linkedin_url.strip() if comp_in.linkedin_url else None,
        decision_maker_name=comp_in.decision_maker_name,
        decision_maker_role=comp_in.decision_maker_role,
        decision_maker_email=comp_in.decision_maker_email,
        decision_maker_linkedin=comp_in.decision_maker_linkedin,
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
            notes=comp_in.source_notes or "Collected during company profiling"
        )
        db.add(source_email)

    if comp_in.public_phone:
        source_phone = ContactSource(
            company_id=company.id,
            field_name="public_phone",
            source_url=source_url,
            source_type="official_website" if comp_in.website else "user_entry",
            notes=comp_in.source_notes or "Public business telephone"
        )
        db.add(source_phone)

    if comp_in.laptop_count_evidence:
        source_laptop = ContactSource(
            company_id=company.id,
            field_name="laptop_count",
            source_url=source_url,
            source_type="verified_documentation",
            notes=comp_in.laptop_count_evidence
        )
        db.add(source_laptop)

    # Automatically create CRM lead
    lead = Lead(company_id=company.id, pipeline_status="new")
    db.add(lead)

    # Initialize consent record for WhatsApp as unconsented by default (strict compliance!)
    if comp_in.public_whatsapp:
        consent_wa = ContactConsent(
            company_id=company.id,
            channel="whatsapp",
            consent_status="unconsented",
            consent_source="Public Directory Listing",
            notes="Requires explicit permission before promotional messages can be sent via Meta Cloud API"
        )
        db.add(consent_wa)

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
    search: Optional[str] = None
) -> Tuple[List[Company], int]:
    query = db.query(Company)

    if city and city.lower() != "all":
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
    companies = query.order_by(Company.id.desc()).offset(skip).limit(limit).all()
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

    # Recalculate laptop verification flag if updated
    if "laptop_count_verified" in update_data or "laptop_count_evidence" in update_data:
        company.has_verified_5_plus_laptops = bool(
            company.laptop_count_verified and
            company.laptop_count_verified >= 5 and
            company.laptop_count_evidence
        )

    company.date_last_verified = datetime.now(timezone.utc)
    db.commit()
    db.refresh(company)
    return company


def add_contact_source(db: Session, source_in: ContactSourceCreate) -> ContactSource:
    source = ContactSource(
        company_id=source_in.company_id,
        contact_id=source_in.contact_id,
        field_name=source_in.field_name,
        source_url=source_in.source_url,
        source_type=source_in.source_type,
        notes=source_in.notes,
        verified_at=datetime.now(timezone.utc)
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def import_companies_from_csv(db: Session, csv_content: str) -> CSVImportSummary:
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
        website = row.get("website") or row.get("Website") or row.get("Official Website")
        public_email = row.get("email") or row.get("Public Email") or row.get("Business Email")
        public_phone = row.get("phone") or row.get("Public Phone") or row.get("Telephone")
        public_whatsapp = row.get("whatsapp") or row.get("WhatsApp") or row.get("WhatsApp Contact")
        industry = row.get("industry") or row.get("Industry") or "Technology"
        state = row.get("state") or row.get("State")
        source_url = row.get("source_url") or row.get("Source URL") or website or "CSV Bulk Import"
        
        # Laptop / Device verification
        laptop_count_str = row.get("laptop_count") or row.get("Laptop Count") or row.get("Verified Laptops")
        laptop_count = None
        if laptop_count_str and laptop_count_str.isdigit():
            laptop_count = int(laptop_count_str)
        laptop_evidence = row.get("laptop_evidence") or row.get("Laptop Evidence")

        # Employee counts
        emp_min_str = row.get("employee_min") or row.get("Min Employees")
        emp_min = int(emp_min_str) if emp_min_str and emp_min_str.isdigit() else None
        emp_max_str = row.get("employee_max") or row.get("Max Employees")
        emp_max = int(emp_max_str) if emp_max_str and emp_max_str.isdigit() else None
        emp_evidence = row.get("employee_evidence") or row.get("Employee Evidence")

        # Decision maker
        dm_name = row.get("decision_maker_name") or row.get("Decision Maker")
        dm_role = row.get("decision_maker_role") or row.get("Decision Maker Role") or row.get("Title")

        # Check for duplicate
        existing = find_duplicate_company(db, name=name, website=website, email=public_email)
        if existing:
            # Update existing company with any new fields
            if website and not existing.website:
                existing.website = website
            if public_email and not existing.public_email:
                existing.public_email = public_email
            if laptop_count and not existing.laptop_count_verified:
                existing.laptop_count_verified = laptop_count
                existing.laptop_count_evidence = laptop_evidence
                existing.has_verified_5_plus_laptops = bool(laptop_count >= 5 and laptop_evidence)
            db.commit()
            updated += 1
            continue

        # Create new company
        has_5_laptops = bool(laptop_count and laptop_count >= 5 and laptop_evidence)
        new_company = Company(
            name=name.strip(),
            website=website.strip() if website else None,
            city=city.strip(),
            state=state.strip() if state else None,
            country="India",
            industry=industry.strip() if industry else None,
            public_email=public_email.strip() if public_email else None,
            public_phone=public_phone.strip() if public_phone else None,
            public_whatsapp=public_whatsapp.strip() if public_whatsapp else None,
            employee_count_min=emp_min,
            employee_count_max=emp_max,
            employee_size_evidence=emp_evidence,
            laptop_count_verified=laptop_count,
            laptop_count_evidence=laptop_evidence,
            has_verified_5_plus_laptops=has_5_laptops,
            decision_maker_name=dm_name,
            decision_maker_role=dm_role,
            date_last_verified=datetime.now(timezone.utc)
        )
        db.add(new_company)
        db.flush()

        # Add Source Record
        source = ContactSource(
            company_id=new_company.id,
            field_name="general_profile",
            source_url=source_url,
            source_type="csv_import",
            notes="Imported via official company batch upload"
        )
        db.add(source)

        # Create Lead
        lead = Lead(company_id=new_company.id, pipeline_status="new")
        db.add(lead)

        # Consent record for WhatsApp
        if public_whatsapp:
            consent_wa = ContactConsent(
                company_id=new_company.id,
                channel="whatsapp",
                consent_status="unconsented",
                consent_source="Public Directory / CSV Import",
                notes="Requires explicit permission before promotional messages can be sent via Meta Cloud API"
            )
            db.add(consent_wa)

        created += 1

    db.commit()
    return CSVImportSummary(
        total_processed=created + updated + skipped,
        created_count=created,
        updated_count=updated,
        duplicate_skipped_count=skipped,
        errors=errors
    )
