import os
import sys
from datetime import datetime, timezone, timedelta

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal, Base, engine
from app.models.user import User
from app.models.company import Company, CompanyContact, ContactSource
from app.models.consent import ContactConsent
from app.models.lead import Lead, Meeting, Trial
from app.models.campaign import Campaign, CampaignRecipient
from app.models.email import EmailDraft, EmailEvent
from app.models.whatsapp import WhatsAppTemplate, WhatsAppMessage
from app.models.reply import Conversation, Reply
from app.services.auth_service import get_password_hash, seed_default_admin
from app.services.whatsapp_service import seed_default_meta_templates
from app.services.email_generator_service import generate_email_draft
from app.services.qualification_service import qualify_company


def run_seed():
    print("Initializing ActTrident Database Tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print("1. Seeding Users...")
        admin = seed_default_admin(db)
        
        rep = db.query(User).filter(User.email == "sales@acttrident.ai").first()
        if not rep:
            rep = User(
                email="sales@acttrident.ai",
                hashed_password=get_password_hash("SalesPassword2026!"),
                full_name="ActTrident BD Specialist",
                role="sales_rep"
            )
            db.add(rep)
            db.commit()

        print("2. Seeding Approved Meta WhatsApp Templates...")
        seed_default_meta_templates(db)

        print("3. Seeding Target Companies across Siliguri, Gangtok, Patna, Bhagalpur...")
        sample_companies = [
            # Siliguri
            {
                "name": "Siliguri Cloud Networks",
                "website": "https://siliguricloud.example.com",
                "industry": "Software Development",
                "description": "Custom enterprise software and cloud hosting solutions for North Bengal.",
                "city": "Siliguri",
                "state": "West Bengal",
                "public_email": "contact@siliguricloud.example.com",
                "public_phone": "+91-353-2551000",
                "public_whatsapp": "+91-9832001000",
                "laptop_count_verified": 12,
                "laptop_count_evidence": "Careers portal specifies company-issued Dell Latitude laptops for hybrid developers",
                "employee_count_min": 15,
                "employee_count_max": 30,
                "employee_size_evidence": "MCA annual return lists 22 full-time staff",
                "decision_maker_name": "Anirban Mukherjee",
                "decision_maker_role": "Managing Director",
                "source_url": "https://siliguricloud.example.com/careers"
            },
            # Gangtok
            {
                "name": "Himalayan Digital Works",
                "website": "https://himalayandigital.example.com",
                "industry": "IT Services",
                "description": "Managed cloud services, VoIP telephony, and remote infrastructure.",
                "city": "Gangtok",
                "state": "Sikkim",
                "public_email": "hello@himalayandigital.example.com",
                "public_phone": "+91-3592-201111",
                "public_whatsapp": "+91-9733001111",
                "laptop_count_verified": 8,
                "laptop_count_evidence": "Official office setup policy details 8 dedicated ThinkPads",
                "employee_count_min": 10,
                "employee_count_max": 20,
                "employee_size_evidence": "Startup Sikkim portal listing 14 developers",
                "decision_maker_name": "Karma Wangdi",
                "decision_maker_role": "Chief Technology Officer",
                "source_url": "https://sikkim.gov.in/startups/himalayan-digital"
            },
            # Patna
            {
                "name": "Patna Software Systems",
                "website": "https://patnasoft.example.com",
                "industry": "Software Development",
                "description": "High-volume government web portals and banking integrations.",
                "city": "Patna",
                "state": "Bihar",
                "public_email": "info@patnasoft.example.com",
                "public_phone": "+91-612-2244000",
                "public_whatsapp": "+91-9431004000",
                "laptop_count_verified": 22,
                "laptop_count_evidence": "IT procurement audit confirms 22 managed HP workstations",
                "employee_count_min": 30,
                "employee_count_max": 60,
                "employee_size_evidence": "Bihar IT Association roster lists 45 developers",
                "decision_maker_name": "Sunil Kumar",
                "decision_maker_role": "VP Engineering",
                "source_url": "https://biharitassociation.org/members/patna-soft"
            },
            # Bhagalpur
            {
                "name": "Anga Tech Innovations",
                "website": "https://angatech.example.com",
                "industry": "Digital Marketing",
                "description": "E-commerce growth engineering and cloud retail systems.",
                "city": "Bhagalpur",
                "state": "Bihar",
                "public_email": "connect@angatech.example.com",
                "public_phone": "+91-641-2401234",
                "public_whatsapp": "+91-9470001234",
                "laptop_count_verified": 7,
                "laptop_count_evidence": "Office infrastructure report logs 7 active Asus laptops",
                "employee_count_min": 8,
                "employee_count_max": 15,
                "employee_size_evidence": "MSME enterprise certification",
                "decision_maker_name": "Alok Pandey",
                "decision_maker_role": "Founder & CEO",
                "source_url": "https://angatech.example.com/about"
            }
        ]

        created_companies = []
        for cdata in sample_companies:
            existing = db.query(Company).filter(Company.name == cdata["name"]).first()
            if not existing:
                comp = Company(
                    name=cdata["name"],
                    website=cdata["website"],
                    industry=cdata["industry"],
                    description=cdata["description"],
                    city=cdata["city"],
                    state=cdata["state"],
                    country="India",
                    public_email=cdata["public_email"],
                    public_phone=cdata["public_phone"],
                    public_whatsapp=cdata["public_whatsapp"],
                    laptop_count_verified=cdata["laptop_count_verified"],
                    laptop_count_evidence=cdata["laptop_count_evidence"],
                    has_verified_5_plus_laptops=True,
                    employee_count_min=cdata["employee_count_min"],
                    employee_count_max=cdata["employee_count_max"],
                    employee_size_evidence=cdata["employee_size_evidence"],
                    decision_maker_name=cdata["decision_maker_name"],
                    decision_maker_role=cdata["decision_maker_role"],
                    date_last_verified=datetime.now(timezone.utc)
                )
                db.add(comp)
                db.flush()

                # Source attribution
                src = ContactSource(
                    company_id=comp.id,
                    field_name="profile_and_laptops",
                    source_url=cdata["source_url"],
                    source_type="official_documentation",
                    notes="Verified verified laptop fleet & decision-maker information"
                )
                db.add(src)

                # CRM lead
                lead = Lead(company_id=comp.id, pipeline_status="new")
                db.add(lead)

                # WhatsApp consent default unconsented
                consent = ContactConsent(
                    company_id=comp.id,
                    channel="whatsapp",
                    consent_status="unconsented",
                    consent_source="Public Directory Listing",
                    notes="Compliance lock: requires explicit recorded consent before Meta Cloud API automated send"
                )
                db.add(consent)

                # Run qualification
                qualify_company(db, comp)
                created_companies.append(comp)
            else:
                created_companies.append(existing)

        db.commit()

        print("4. Seeding Geographic Campaigns...")
        campaign_configs = [
            ("Siliguri IT Companies Campaign", "Siliguri", "Acquire West Bengal tech SMBs for ActTrident 90-day evaluation"),
            ("Sikkim Technology Companies Campaign", "Gangtok", "Engage Gangtok IT services and startups for managed device security"),
            ("Patna Software Companies Campaign", "Patna", "Target high-density Bihar enterprise software development teams"),
            ("Bhagalpur Business Outreach Campaign", "Bhagalpur", "Introduce lightweight browser workspace protection to regional agencies")
        ]

        for c_name, c_city, c_obj in campaign_configs:
            existing_camp = db.query(Campaign).filter(Campaign.name == c_name).first()
            if not existing_camp:
                camp = Campaign(
                    name=c_name,
                    target_city=c_city,
                    objective=c_obj,
                    status="draft",  # Always default to draft!
                    daily_email_limit=50,
                    daily_whatsapp_limit=20,
                    sending_schedule="09:00-18:00 IST Weekdays"
                )
                db.add(camp)
                db.flush()

                # Associate matching city companies
                matching_comps = [c for c in created_companies if c.city == c_city]
                for mc in matching_comps:
                    rec = CampaignRecipient(campaign_id=camp.id, company_id=mc.id, status="pending")
                    db.add(rec)
                    # Generate sample draft
                    generate_email_draft(db, mc, campaign_id=camp.id, tone="Friendly professional")

        db.commit()
        print("Database Seed Completed Successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
