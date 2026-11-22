import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.company import Company
from app.schemas.research import QualificationResult, QualificationFactorResult

TECH_INDUSTRIES = [
    "software", "information technology", "it services", "digital marketing",
    "saas", "tech consulting", "bpo", "computer training", "cloud", "web development",
    "cybersecurity", "fintech", "edtech", "e-commerce"
]


def qualify_company(db: Session, company: Company) -> QualificationResult:
    factors: List[QualificationFactorResult] = []
    total_score = 0.0

    # Primary source reference
    primary_source = company.sources[0].source_url if (company.sources and len(company.sources) > 0) else (company.website or "Direct verification")

    # Factor 1: Is the company technology-related? (Weight: 20%)
    industry_str = (company.industry or "").lower()
    desc_str = (company.description or "").lower()
    is_tech = any(t in industry_str or t in desc_str for t in TECH_INDUSTRIES)
    f1_score = 20.0 if is_tech else 0.0
    total_score += f1_score
    factors.append(QualificationFactorResult(
        factor_name="Is the company technology-related?",
        passed=is_tech,
        score_weight=f1_score,
        evidence=f"Industry '{company.industry or 'Unspecified'}' {'aligns with technology/digital sector' if is_tech else 'is non-technical or general'}",
        evidence_source=company.website or "Company Registry / MSME Profile",
        verification_state="VERIFIED" if is_tech else "UNKNOWN",
        confidence=0.95 if is_tech else 0.70,
        explanation="ActTrident workspace security solutions specifically protect developers, IT staff, and digital operators handling code and cloud infrastructure."
    ))

    # Factor 2: Does it employ at least five people? (Weight: 15%)
    emp_min = company.employee_count_min or 0
    emp_max = company.employee_count_max or 0
    has_5_emp = (emp_min >= 5) or (emp_max >= 5)
    f2_score = 15.0 if has_5_emp else 0.0
    total_score += f2_score
    factors.append(QualificationFactorResult(
        factor_name="Does it employ at least five people?",
        passed=has_5_emp,
        score_weight=f2_score,
        evidence=f"Employee range {emp_min}-{emp_max}. Evidence: {company.employee_size_evidence or 'Not documented'}",
        evidence_source=primary_source,
        verification_state="VERIFIED" if (has_5_emp and company.employee_size_evidence) else ("CLAIMED" if has_5_emp else "UNKNOWN"),
        confidence=0.90 if has_5_emp else 0.50,
        explanation="Separated from laptop fleet evidence. Minimum headcount confirms operational viability for team-based product trials."
    ))

    # Factor 3: Is there evidence of company-managed laptops? (Weight: 25%) - STRICT!
    has_laptop_evidence = bool(
        company.laptop_count_verified and
        company.laptop_count_verified >= 5 and
        company.laptop_count_evidence
    )
    if has_laptop_evidence:
        f3_score = 25.0
        evidence_f3 = f"Verified {company.laptop_count_verified} laptops: {company.laptop_count_evidence}"
        conf_f3 = 0.95
        v_state_3 = "VERIFIED"
        expl_f3 = "Documented proof confirms 5+ active company-managed devices eligible for the proposed 90-day evaluation."
    elif company.laptop_count_verified and company.laptop_count_verified >= 5:
        f3_score = 0.0
        evidence_f3 = f"Claimed {company.laptop_count_verified} laptops but lacks documented source evidence (Cannot verify without confirmation)"
        conf_f3 = 0.40
        v_state_3 = "CLAIMED"
        expl_f3 = "Under ActTrident truthfulness policy, device counts require corroborated corporate evidence before awarding qualification points."
    else:
        f3_score = 0.0
        evidence_f3 = "No documented evidence of 5+ company-managed laptops"
        conf_f3 = 0.30
        v_state_3 = "UNKNOWN"
        expl_f3 = "Fleet evidence unknown or under 5 laptops."
    total_score += f3_score
    factors.append(QualificationFactorResult(
        factor_name="Is there evidence of company-managed laptops?",
        passed=has_laptop_evidence,
        score_weight=f3_score,
        evidence=evidence_f3,
        evidence_source=primary_source,
        verification_state=v_state_3,
        confidence=conf_f3,
        explanation=expl_f3
    ))

    # Factor 4: Does it use browser-based workflows? (Weight: 10%)
    BROWSER_WORKFLOW_KEYWORDS = ["saas", "cloud", "portal", "web application", "crm", "dashboard", "developer", "remote", "web-based", "platform", "online", "software", "digital", "website", "tech"]
    browser_workflows = any(k in desc_str or k in industry_str for k in BROWSER_WORKFLOW_KEYWORDS)
    f4_score = 10.0 if browser_workflows else 0.0
    total_score += f4_score
    factors.append(QualificationFactorResult(
        factor_name="Does it use browser-based workflows?",
        passed=browser_workflows,
        score_weight=f4_score,
        evidence="Web-based operations indicated by official online presence and digital service portfolio" if browser_workflows else "Limited online workflow evidence",
        evidence_source=company.website or "Domain DNS records",
        verification_state="VERIFIED" if (company.website and any(k in desc_str or k in industry_str for k in ["saas", "cloud", "portal", "web application", "software"])) else ("CLAIMED" if browser_workflows else "UNKNOWN"),
        confidence=0.85 if browser_workflows else 0.40,
        explanation="Browser workspace isolation delivers immediate security against web-borne data exfiltration."
    ))

    # Factor 5: Does it handle customer or business information? (Weight: 10%)
    DATA_KEYWORDS = ["client", "customer", "bpo", "financial", "database", "analytics", "patient", "user", "confidential", "deliverables", "records", "software", "development", "it services"]
    handles_data = any(k in desc_str or k in industry_str for k in DATA_KEYWORDS)
    f5_score = 10.0 if handles_data else 0.0
    total_score += f5_score
    factors.append(QualificationFactorResult(
        factor_name="Does it handle customer or business information?",
        passed=handles_data,
        score_weight=f5_score,
        evidence="Business model processes client deliverables, project files, and customer account credentials" if handles_data else "General business records",
        evidence_source=company.website or "Public business description",
        verification_state="VERIFIED" if handles_data else "UNKNOWN",
        confidence=0.85 if handles_data else 0.40,
        explanation="Client confidentiality obligations make compliance and data security a high executive priority."
    ))

    # Factor 6: Does its business model make ActTrident relevant? (Weight: 10%)
    relevance = is_tech and (has_laptop_evidence or has_5_emp)
    f6_score = 10.0 if relevance else 0.0
    total_score += f6_score
    factors.append(QualificationFactorResult(
        factor_name="Does its business model make ActTrident relevant?",
        passed=relevance,
        score_weight=f6_score,
        evidence="High fit for ActTrident workspace protection and managed laptop fleet oversight" if relevance else "Secondary fit pending device verification",
        evidence_source="ActTrident Target Market Heuristic",
        verification_state="VERIFIED" if relevance else "UNKNOWN",
        confidence=0.90 if relevance else 0.40,
        explanation="Focuses outreach resources exclusively on prospects where ActTrident provides tangible ROI."
    ))

    # Factor 7: Is there an accessible business contact channel? (Weight: 10%)
    has_email = bool(company.public_email or company.decision_maker_email)
    has_phone = bool(company.public_phone or company.public_whatsapp)
    has_contact = has_email or has_phone
    f7_score = 10.0 if has_email else (5.0 if has_phone else 0.0)
    total_score += f7_score
    contact_details = []
    if company.public_email:
        contact_details.append(f"Email: {company.public_email}")
    if company.public_phone:
        contact_details.append(f"Phone: {company.public_phone}")
    if company.public_whatsapp:
        contact_details.append(f"WhatsApp: {company.public_whatsapp}")
    factors.append(QualificationFactorResult(
        factor_name="Is there an accessible business contact channel?",
        passed=has_contact,
        score_weight=f7_score,
        evidence=", ".join(contact_details) if contact_details else "No public business contact channel verified",
        evidence_source=primary_source,
        verification_state="VERIFIED" if has_email else ("CLAIMED" if has_phone else "UNKNOWN"),
        confidence=1.0 if has_email else (0.70 if has_phone else 0.0),
        explanation="Outreach requires an authenticated, non-private business email or WhatsApp channel."
    ))

    # Determine Classification Status & Recommended Next Action
    if total_score >= 80.0 and has_laptop_evidence:
        status = "High priority"
        reason = f"Excellent candidate for ActTrident 90-day evaluation: verified {company.laptop_count_verified} managed laptops, tech sector, accessible contact."
        action = "Generate AI email draft and route to manager approval queue for 90-day evaluation invitation."
    elif total_score >= 60.0:
        if not has_laptop_evidence:
            status = "Needs manual verification"
            reason = "Matches technology and employee size criteria, but managed laptop count (5+) requires manual confirmation."
            action = "Dispatch research specialist to review careers page, MCA filings, or LinkedIn office tours for fleet evidence."
        else:
            status = "Medium priority"
            reason = "Meets core technology and device criteria with moderate overall fit."
            action = "Draft introductory outreach proposing preliminary capabilities review."
    elif total_score >= 40.0:
        status = "Low priority"
        reason = "Limited technology fit or insufficient contact channels available."
        action = "Monitor for future expansion or secondary outreach cycle."
    else:
        status = "Not suitable"
        reason = "Does not align with ActTrident target criteria for managed laptop deployments."
        action = "Archive lead record to suppression list."

    v_status = getattr(company, "verification_status", None) or ("demo_fixture" if company.is_demo else "unverified")
    if company.is_demo or v_status == "demo_fixture":
        reason = f"[DEMO FIXTURE — NOT FOR LIVE OUTREACH] {reason}"

    distinction_note = (
        f"Verification status: {v_status}. "
        f"Employee count ({company.employee_count_min or 'Unknown'}-{company.employee_count_max or 'Unknown'}) "
        f"is distinct from verified laptop count ({company.laptop_count_verified or 'Unknown / None verified'}). "
        "This score is a transparent heuristic prioritization aid based on currently recorded evidence, not objective certainty. "
        "Per ActTrident truthfulness guidelines, 5+ laptops are only certified when supported by documented evidence."
    )

    now_utc = datetime.now(timezone.utc)

    result = QualificationResult(
        company_id=company.id,
        score=round(total_score, 1),
        status=status,
        reason=reason,
        factors=factors,
        has_verified_5_plus_laptops=has_laptop_evidence,
        distinction_note=distinction_note,
        recommended_next_action=action,
        last_verified_at=now_utc,
        is_stale=False
    )

    # Persist in Company record
    company.qualification_score = result.score
    company.qualification_status = result.status
    company.qualification_reason = result.reason
    company.qualification_factors = json.dumps([f.model_dump() for f in factors])
    company.has_verified_5_plus_laptops = has_laptop_evidence
    company.date_last_verified = now_utc

    # If lead exists, update pipeline status
    if company.lead:
        if status in ["High priority", "Medium priority"]:
            company.lead.pipeline_status = "qualified"
        elif status == "Needs manual verification":
            company.lead.pipeline_status = "researching"

    db.commit()
    return result


def reverify_stale_qualifications(db: Session, max_age_days: int = 30) -> List[QualificationResult]:
    """
    Scans company records whose qualification evidence is older than max_age_days
    and re-runs the qualification engine.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    stale_companies = db.query(Company).filter(
        Company.is_demo == False,
        (Company.date_last_verified == None) | (Company.date_last_verified < cutoff)
    ).limit(50).all()

    results = []
    for company in stale_companies:
        res = qualify_company(db, company)
        results.append(res)
    return results
