import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.service_catalogue import ServiceCatalogueItem
from app.schemas.service_catalogue import ServiceCatalogueCreate, ServiceCatalogueUpdate, ServiceMatchResult

logger = logging.getLogger(__name__)

DEFAULT_SERVICE_ITEMS = [
    {
        "service_code": "ACT-WS-01",
        "service_name": "Secure Workspace & Endpoint Isolation",
        "description": "Local-first isolated browser workspaces and secure virtual sandboxes preventing remote developer code leakage, unauthorized clipboard copying, and web malware exfiltration.",
        "target_business_types": [
            "software development", "it services", "saas", "fintech", "bpo",
            "remote consulting", "edtech", "web development", "mobile app development"
        ],
        "common_business_problems": [
            "unmanaged remote employee laptops",
            "risk of source code theft or leakage",
            "unauthorized copy-pasting of sensitive customer data",
            "web malware and phishing via employee browser",
            "lack of developer endpoint compliance"
        ],
        "required_qualification_signals": {
            "min_score": 60,
            "target_signals": ["software", "developer", "remote", "it_services", "data_handling"]
        },
        "approved_claims": [
            "Isolated browser-based workspace preventing code/data exfiltration",
            "Zero-trust credential shielding for SaaS and internal tools",
            "Centralized security controls without intrusive device surveillance",
            "Lightweight deployment without complex hardware appliance setup"
        ],
        "disallowed_claims": [
            "90-day evaluation without qualification",
            "100% hack-proof guarantee",
            "Military-grade impenetrable security",
            "Replaces all firewalls and antivirus tools instantly",
            "Zero vulnerability promise"
        ],
        "discovery_questions": [
            "Do remote developers or contractors access internal source repositories from personal machines?",
            "How is client IP and sensitive API keys protected on employee browsers?",
            "Are engineering endpoints audited for unauthorized data exfiltration or malware risks?"
        ],
        "outreach_templates": {
            "professional": {
                "subject": "Securing distributed developer endpoints at {company_name}",
                "body": "Hi {contact_name},\n\nNoticed {company_name}'s focus on {industry}. As engineering teams scale distributed workflows, protecting proprietary code repositories and SaaS credentials across developer laptops becomes a primary operational priority.\n\nActTrident provides lightweight workspace isolation that prevents data leakage and credential theft without slowing down your engineering velocity.\n\nWould you be open to a brief technical exchange this week?\n\nBest regards,\nActTrident Team"
            },
            "concise": {
                "subject": "Code & credential isolation for {company_name}",
                "body": "Hi {contact_name},\n\nReaching out because {company_name} develops proprietary software. ActTrident secures developer endpoints by isolating cloud workspaces and preventing code exfiltration.\n\nHappy to share a 3-minute technical overview if this is on your radar.\n\nBest,\nActTrident Team"
            },
            "consultative": {
                "subject": "Addressing endpoint security risks for {company_name}'s tech stack",
                "body": "Hi {contact_name},\n\nMany tech firms in {city} are navigating the balance between developer speed and client data protection across remote machines.\n\nActTrident's workspace isolation helps technology firms safeguard proprietary code without imposing heavy MDM surveillance on developers.\n\nWould you be open to exploring whether this fits {company_name}'s current security posture?\n\nWarm regards,\nActTrident Team"
            },
            "technical": {
                "subject": "Zero-trust session & clipboard sandboxing for {company_name}",
                "body": "Hi {contact_name},\n\nGiven {company_name}'s technical footprint in {industry}, we developed ActTrident to provide hardware-accelerated browser sandboxing and ephemeral session protection for software engineers.\n\nIt isolates repo access, shields API tokens in memory, and prevents clipboard exfiltration.\n\nOpen to reviewing our architecture brief?\n\nRegards,\nActTrident Engineering"
            }
        },
        "is_active": True
    },
    {
        "service_code": "ACT-CL-02",
        "service_name": "Cloud Infrastructure & SaaS Credential Protection",
        "description": "Enterprise credential shielding, ephemeral production access, and session isolation preventing accidental exposure of cloud tokens, API keys, and production admin dashboards.",
        "target_business_types": [
            "cloud consulting", "devops", "ecommerce", "digital agency", "fintech",
            "telecom", "cybersecurity", "hosting", "cloud infrastructure", "cloud"
        ],
        "common_business_problems": [
            "accidental exposure of cloud API tokens",
            "credential stuffing against internal SaaS",
            "lack of session isolation for admin consoles",
            "storing unencrypted credentials on developer machines",
            "unauthorized production cloud access"
        ],
        "required_qualification_signals": {
            "min_score": 60,
            "target_signals": ["cloud", "devops", "aws", "gcp", "azure", "saas", "infrastructure"]
        },
        "approved_claims": [
            "Real-time token shielding preventing credential extraction from developer memory",
            "Encrypted ephemeral sessions for production cloud dashboards",
            "Audit-ready access logging compliant with modern security frameworks",
            "Zero persistent credential storage on local workstations"
        ],
        "disallowed_claims": [
            "Complete automated cloud compliance without human audit",
            "Zero setup effort guaranteed in 10 seconds",
            "Free lifetime enterprise tier",
            "Eliminates 100% of insider threats automatically"
        ],
        "discovery_questions": [
            "How are AWS/GCP production tokens isolated on developer workstations?",
            "What prevents active session cookies from being hijacked if a workstation is compromised?",
            "How do you enforce ephemeral access for production database consoles?"
        ],
        "outreach_templates": {
            "professional": {
                "subject": "Protecting cloud credentials and admin sessions at {company_name}",
                "body": "Hi {contact_name},\n\nGiven {company_name}'s focus on cloud systems and digital services, safeguarding privileged console sessions and cloud credentials from malware or accidental leakage is crucial.\n\nActTrident provides automated credential shielding and session isolation tailored for high-velocity engineering teams.\n\nCould we share a short summary of how this works?\n\nBest regards,\nActTrident Team"
            },
            "concise": {
                "subject": "Cloud session & credential protection for {company_name}",
                "body": "Hi {contact_name},\n\nActTrident protects cloud credentials and AWS/GCP admin sessions from being extracted from engineer workstations.\n\nOpen to seeing a 2-minute workflow breakdown for {company_name}?\n\nBest,\nActTrident Team"
            },
            "consultative": {
                "subject": "Securing cloud console access across {company_name}'s infrastructure",
                "body": "Hi {contact_name},\n\nAs cloud environments grow, credential sprawl and persistent session tokens on developer machines represent an increasing security risk.\n\nActTrident's cloud credential shielding ensures ephemeral, tamper-proof access to management consoles without breaking existing CI/CD or admin tooling.\n\nWould you be open to a 5-minute conversation on this?\n\nBest regards,\nActTrident Team"
            },
            "technical": {
                "subject": "Ephemeral session shielding for AWS/GCP console access at {company_name}",
                "body": "Hi {contact_name},\n\nWe built ActTrident's credential shielding engine to automatically inject ephemeral tokens into production consoles while encrypting developer session state in memory.\n\nIt eliminates plaintext credentials on developer machines and blocks token exfiltration.\n\nWould you like to examine our security whitepaper?\n\nRegards,\nActTrident Engineering"
            }
        },
        "is_active": True
    },
    {
        "service_code": "ACT-AU-03",
        "service_name": "Local-First B2B Outreach & Sales Operations Automation",
        "description": "Compliant, local-first B2B prospect discovery, contact verification, and AI outreach synthesis with human-in-the-loop review and zero cloud data leaks.",
        "target_business_types": [
            "b2b services", "it staffing", "marketing agency", "business consulting",
            "enterprise software", "recruitment", "digital marketing", "consulting", "technology services"
        ],
        "common_business_problems": [
            "slow manual prospect research",
            "unverified emails bouncing and harming domain reputation",
            "generic irrelevant cold emails causing spam complaints",
            "lack of clear follow-up tracking",
            "relying on sketchy scraping databases"
        ],
        "required_qualification_signals": {
            "min_score": 50,
            "target_signals": ["b2b", "services", "consulting", "marketing", "agency", "staffing"]
        },
        "approved_claims": [
            "Local-first prospect discovery with multi-source validation",
            "Multi-stage contact verification protecting sender domain reputation",
            "Evidence-based AI research dossiers tailored to prospect business context",
            "Human-in-the-loop approval workflow for all outbound communications"
        ],
        "disallowed_claims": [
            "100% reply rate guarantee",
            "Send 100,000 cold emails daily without being flagged",
            "Scrapes private unlisted emails from behind firewalls",
            "Guaranteed closed enterprise deals in 30 days"
        ],
        "discovery_questions": [
            "How much engineering or sales time is spent on prospect verification and research?",
            "What guardrails are in place to prevent unvetted outreach from damaging your domain reputation?",
            "How do you ensure outreach messages reference verifiable business facts?"
        ],
        "outreach_templates": {
            "professional": {
                "subject": "Streamlining verified B2B outreach for {company_name}",
                "body": "Hi {contact_name},\n\nWe noticed {company_name}'s presence in {city}'s technology ecosystem. Reaching B2B decision-makers with relevant, verified information often requires hours of manual research.\n\nActTrident automates prospect discovery and technical qualification with strict verification guardrails and human review.\n\nWould you be open to seeing how other B2B firms use this to drive qualified meetings?\n\nBest regards,\nActTrident Team"
            },
            "concise": {
                "subject": "Verified B2B pipeline generation for {company_name}",
                "body": "Hi {contact_name},\n\nReaching out because {company_name} offers professional B2B services. ActTrident automates prospect discovery with DNS verification and human review to safeguard sender reputation.\n\nWould you like a quick overview?\n\nBest,\nActTrident Team"
            },
            "consultative": {
                "subject": "High-integrity outbound sales operations for {company_name}",
                "body": "Hi {contact_name},\n\nFor firms delivering B2B services, generic cold outreach often leads to low engagement and email deliverability penalties.\n\nActTrident combines local intelligence, verified public channels, and human approval to maintain high conversion and clean domain reputation.\n\nCould we share a few brief examples with your team?\n\nBest regards,\nActTrident Team"
            },
            "technical": {
                "subject": "Architecture review: local-first verifiable sales automation for {company_name}",
                "body": "Hi {contact_name},\n\nWe engineered ActTrident as a local-first B2B intelligence engine: DNS MX validation, strict cryptographic approval gates, and zero third-party data leaks.\n\nOpen to reviewing our technical workflow overview for {company_name}?\n\nRegards,\nActTrident Engineering"
            }
        },
        "is_active": True
    }
]


def seed_default_services(db: Session) -> int:
    """
    Seeds default compliant ActTrident services if table is empty.
    Returns count of services seeded.
    """
    try:
        count = db.query(ServiceCatalogueItem).count()
        if count > 0:
            return 0

        seeded_count = 0
        for item_data in DEFAULT_SERVICE_ITEMS:
            svc = ServiceCatalogueItem(
                service_code=item_data["service_code"],
                service_name=item_data["service_name"],
                description=item_data["description"],
                target_business_types=item_data["target_business_types"],
                common_business_problems=item_data["common_business_problems"],
                required_qualification_signals=item_data["required_qualification_signals"],
                approved_claims=item_data["approved_claims"],
                disallowed_claims=item_data["disallowed_claims"],
                discovery_questions=item_data.get("discovery_questions", []),
                outreach_templates=item_data.get("outreach_templates", {}),
                is_active=item_data.get("is_active", True)
            )
            db.add(svc)
            seeded_count += 1
        db.commit()
        logger.info(f"Seeded {seeded_count} default ActTrident service catalogue items")
        return seeded_count
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to seed default service catalogue: {exc}")
        return 0


def get_services(db: Session, active_only: bool = False) -> List[ServiceCatalogueItem]:
    query = db.query(ServiceCatalogueItem)
    if active_only:
        query = query.filter(ServiceCatalogueItem.is_active == True)
    return query.order_by(ServiceCatalogueItem.id.asc()).all()


def get_service_by_id(db: Session, service_id: int) -> Optional[ServiceCatalogueItem]:
    return db.query(ServiceCatalogueItem).filter(ServiceCatalogueItem.id == service_id).first()


def get_service_by_code(db: Session, service_code: str) -> Optional[ServiceCatalogueItem]:
    return db.query(ServiceCatalogueItem).filter(ServiceCatalogueItem.service_code == service_code).first()


def create_service(db: Session, item_in: ServiceCatalogueCreate) -> ServiceCatalogueItem:
    svc = ServiceCatalogueItem(
        service_code=item_in.service_code,
        service_name=item_in.service_name,
        description=item_in.description,
        target_business_types=item_in.target_business_types,
        common_business_problems=item_in.common_business_problems,
        required_qualification_signals=item_in.required_qualification_signals,
        approved_claims=item_in.approved_claims,
        disallowed_claims=item_in.disallowed_claims,
        discovery_questions=item_in.discovery_questions or [],
        outreach_templates=item_in.outreach_templates or {},
        is_active=item_in.is_active
    )
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


def update_service(db: Session, service_id: int, item_in: ServiceCatalogueUpdate) -> Optional[ServiceCatalogueItem]:
    svc = get_service_by_id(db, service_id)
    if not svc:
        return None

    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(svc, field, value)

    db.commit()
    db.refresh(svc)
    return svc


def delete_service(db: Session, service_id: int) -> bool:
    svc = get_service_by_id(db, service_id)
    if not svc:
        return False
    db.delete(svc)
    db.commit()
    return True


def match_service_for_company(
    company_or_data: Any,
    catalogue: Optional[List[ServiceCatalogueItem]] = None,
    db: Optional[Session] = None
) -> Optional[ServiceMatchResult]:
    """
    Intelligently matches a business against active ActTrident services.
    Extracts signals from industry, name, description, website, and technology keywords.
    Computes a match score per service and selects the best fit with explicit rationale.
    """
    # Load catalogue if not provided
    if catalogue is None:
        if db is not None:
            catalogue = get_services(db, active_only=True)
        else:
            # Fallback to defaults
            catalogue = [
                ServiceCatalogueItem(
                    id=i + 1,
                    service_code=item["service_code"],
                    service_name=item["service_name"],
                    description=item["description"],
                    target_business_types=item["target_business_types"],
                    common_business_problems=item["common_business_problems"],
                    required_qualification_signals=item["required_qualification_signals"],
                    approved_claims=item["approved_claims"],
                    disallowed_claims=item["disallowed_claims"],
                    discovery_questions=item.get("discovery_questions", []),
                    outreach_templates=item.get("outreach_templates", {}),
                    is_active=True
                )
                for i, item in enumerate(DEFAULT_SERVICE_ITEMS)
            ]

    if not catalogue:
        return None

    # Extract company attributes
    if isinstance(company_or_data, dict):
        name = company_or_data.get("name") or ""
        industry = company_or_data.get("industry") or ""
        description = company_or_data.get("description") or ""
        website = company_or_data.get("website") or ""
    else:
        name = getattr(company_or_data, "name", "") or ""
        industry = getattr(company_or_data, "industry", "") or ""
        description = getattr(company_or_data, "description", "") or ""
        website = getattr(company_or_data, "website", "") or ""

    text_corpus = f"{name} {industry} {description} {website}".lower()

    best_match: Optional[ServiceCatalogueItem] = None
    best_score = 0.0
    best_rationale = ""
    best_angle = ""

    for svc in catalogue:
        if not svc.is_active:
            continue

        match_score = 0.0
        matched_types = []
        matched_problems = []

        # Check target business types
        for bt in (svc.target_business_types or []):
            bt_clean = bt.lower().strip()
            if bt_clean in text_corpus:
                match_score += 25.0
                matched_types.append(bt)

        # Check common business problems / relevant keywords
        for bp in (svc.common_business_problems or []):
            words = [w for w in bp.lower().split() if len(w) > 3]
            overlap = [w for w in words if w in text_corpus]
            if len(overlap) >= 2:
                match_score += 15.0
                matched_problems.append(bp)
            elif len(overlap) == 1:
                match_score += 5.0

        # Specific heuristics based on service code
        if svc.service_code == "ACT-WS-01":
            if any(k in text_corpus for k in ["software", "developer", "engineering", "coding", "full stack", "tech labs"]):
                match_score += 30.0
            if any(k in text_corpus for k in ["remote", "offshore", "dedicated team"]):
                match_score += 15.0
        elif svc.service_code == "ACT-CL-02":
            if any(k in text_corpus for k in ["cloud", "devops", "aws", "gcp", "azure", "docker", "kubernetes", "hosting"]):
                match_score += 35.0
        elif svc.service_code == "ACT-AU-03":
            if any(k in text_corpus for k in ["marketing", "b2b", "agency", "consulting", "staffing", "sales", "business solutions"]):
                match_score += 30.0

        # Normalize score
        normalized_confidence = min(round(match_score / 100.0, 2), 0.98)
        if normalized_confidence == 0.0:
            # Baseline compatibility score for generic tech
            normalized_confidence = 0.35

        if match_score > best_score:
            best_score = match_score
            best_match = svc
            reasons = []
            if matched_types:
                reasons.append(f"Industry alignment with {', '.join(matched_types[:2])}")
            if matched_problems:
                reasons.append(f"Solves operational challenges around {matched_problems[0]}")
            if not reasons:
                reasons.append(f"Aligned with core {svc.service_name} operational profile")
            best_rationale = "; ".join(reasons)
            
            if svc.service_code == "ACT-WS-01":
                best_angle = "Developer endpoint security & code exfiltration prevention"
            elif svc.service_code == "ACT-CL-02":
                best_angle = "Ephemeral cloud credential shielding & console protection"
            else:
                best_angle = "Verified B2B outreach & sender domain protection"

    # Default to first active service if no specific high score
    if not best_match and catalogue:
        best_match = catalogue[0]
        best_score = 40.0
        best_rationale = f"Matched to primary ActTrident service {best_match.service_name}"
        best_angle = "Endpoint security & workspace isolation"

    confidence = min(max(round(best_score / 100.0, 2), 0.40), 0.98)

    return ServiceMatchResult(
        service_id=best_match.id if best_match.id else 1,
        service_code=best_match.service_code,
        service_name=best_match.service_name,
        match_confidence=confidence,
        rationale=best_rationale,
        recommended_outreach_angle=best_angle
    )
