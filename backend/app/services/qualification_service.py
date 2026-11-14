import json
from typing import Dict, Any, List
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

    # Factor 1: Is the company technology-related? (Weight: 20%)
    industry_str = (company.industry or "").lower()
    desc_str = (company.description or "").lower()
    is_tech = any(t in industry_str or t in desc_str for t in TECH_INDUSTRIES)
    f1_score = 20.0 if is_tech else 5.0
    total_score += f1_score
    factors.append(QualificationFactorResult(
        factor_name="Is the company technology-related?",
        passed=is_tech,
        score_weight=f1_score,
        evidence=f"Industry '{company.industry or 'Unspecified'}' {'aligns with technology/digital sector' if is_tech else 'is non-technical or general'}"
    ))

    # Factor 2: Does it employ at least five people? (Weight: 15%)
    emp_min = company.employee_count_min or 0
    emp_max = company.employee_count_max or 0
    has_5_emp = (emp_min >= 5) or (emp_max >= 5)
    f2_score = 15.0 if has_5_emp else (5.0 if emp_max > 0 else 0.0)
    total_score += f2_score
    factors.append(QualificationFactorResult(
        factor_name="Does it employ at least five people?",
        passed=has_5_emp,
        score_weight=f2_score,
        evidence=f"Employee range {emp_min}-{emp_max}. Evidence: {company.employee_size_evidence or 'Not documented'}"
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
    elif company.laptop_count_verified and company.laptop_count_verified >= 5:
        f3_score = 10.0
        evidence_f3 = f"Claimed {company.laptop_count_verified} laptops but lacks documented source evidence (Cannot verify without confirmation)"
    else:
        f3_score = 0.0
        evidence_f3 = "No documented evidence of 5+ company-managed laptops"
    total_score += f3_score
    factors.append(QualificationFactorResult(
        factor_name="Is there evidence of company-managed laptops?",
        passed=has_laptop_evidence,
        score_weight=f3_score,
        evidence=evidence_f3
    ))

    # Factor 4: Does it use browser-based workflows? (Weight: 10%)
    browser_workflows = is_tech or bool(company.website)
    f4_score = 10.0 if browser_workflows else 2.0
    total_score += f4_score
    factors.append(QualificationFactorResult(
        factor_name="Does it use browser-based workflows?",
        passed=browser_workflows,
        score_weight=f4_score,
        evidence="Web-based operations indicated by official online presence and digital service portfolio" if browser_workflows else "Limited online workflow evidence"
    ))

    # Factor 5: Does it handle customer or business information? (Weight: 10%)
    handles_data = is_tech or (company.industry in ["BPO", "Financial Services", "IT Services"])
    f5_score = 10.0 if handles_data else 3.0
    total_score += f5_score
    factors.append(QualificationFactorResult(
        factor_name="Does it handle customer or business information?",
        passed=handles_data,
        score_weight=f5_score,
        evidence="Business model processes client deliverables, project files, and customer account credentials" if handles_data else "General business records"
    ))

    # Factor 6: Does its business model make ActTrident relevant? (Weight: 10%)
    relevance = is_tech and (has_laptop_evidence or has_5_emp)
    f6_score = 10.0 if relevance else 2.0
    total_score += f6_score
    factors.append(QualificationFactorResult(
        factor_name="Does its business model make ActTrident relevant?",
        passed=relevance,
        score_weight=f6_score,
        evidence="High fit for ActTrident workspace protection and managed laptop fleet oversight" if relevance else "Secondary fit pending device verification"
    ))

    # Factor 7: Is there an accessible business contact channel? (Weight: 10%)
    has_contact = bool(company.public_email or company.public_phone or company.public_whatsapp)
    f7_score = 10.0 if has_contact else 0.0
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
        evidence=", ".join(contact_details) if contact_details else "No public business contact channel verified"
    ))

    # Determine Classification Status
    if total_score >= 80.0 and has_laptop_evidence:
        status = "High priority"
        reason = f"Excellent candidate for ActTrident 90-day evaluation: verified {company.laptop_count_verified} managed laptops, tech sector, accessible contact."
    elif total_score >= 60.0:
        if not has_laptop_evidence:
            status = "Needs manual verification"
            reason = "Matches technology and employee size criteria, but managed laptop count (5+) requires manual confirmation."
        else:
            status = "Medium priority"
            reason = "Meets core technology and device criteria with moderate overall fit."
    elif total_score >= 40.0:
        status = "Low priority"
        reason = "Limited technology fit or insufficient contact channels available."
    else:
        status = "Not suitable"
        reason = "Does not align with ActTrident target criteria for managed laptop deployments."

    distinction_note = (
        f"Employee count ({company.employee_count_min or 'N/A'}-{company.employee_count_max or 'N/A'}) "
        f"is distinct from verified laptop count ({company.laptop_count_verified or 'None verified'}). "
        "Per ActTrident compliance guidelines, 5+ laptops are only certified when supported by documented evidence."
    )

    result = QualificationResult(
        company_id=company.id,
        score=round(total_score, 1),
        status=status,
        reason=reason,
        factors=factors,
        has_verified_5_plus_laptops=has_laptop_evidence,
        distinction_note=distinction_note
    )

    # Persist in Company record
    company.qualification_score = result.score
    company.qualification_status = result.status
    company.qualification_reason = result.reason
    company.qualification_factors = json.dumps([f.model_dump() for f in factors])
    company.has_verified_5_plus_laptops = has_laptop_evidence

    # If lead exists, update pipeline status
    if company.lead:
        if status in ["High priority", "Medium priority"]:
            company.lead.pipeline_status = "qualified"
        elif status == "Needs manual verification":
            company.lead.pipeline_status = "researching"

    db.commit()
    return result
