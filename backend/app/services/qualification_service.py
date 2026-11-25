import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.company import Company
from app.schemas.research import DiscoveredCompanyItem, QualificationResult, QualificationFactorResult

TECH_INDUSTRIES = [
    "software", "information technology", "it services", "digital marketing",
    "saas", "tech consulting", "bpo", "computer training", "cloud", "web development",
    "cybersecurity", "fintech", "edtech", "e-commerce", "technology", "infotech"
]


def evaluate_discovered_item_qualification(item: DiscoveredCompanyItem) -> Tuple[float, str, str, List[QualificationFactorResult]]:
    """
    Evaluates a DiscoveredCompanyItem in-memory across the seven deterministic qualification dimensions.
    Adheres strictly to the documented 100-point formula:
      1. Technology Alignment:       VERIFIED: 20.0 | CLAIMED: 10.0 | UNKNOWN: 0.0
      2. Workforce Scale (>=5):       VERIFIED: 15.0 | CLAIMED:  7.5 | UNKNOWN: 0.0
      3. Managed Laptop Fleet (>=5):  VERIFIED: 20.0 | CLAIMED: 10.0 | UNKNOWN: 0.0
      4. Browser-Based Workflows:     VERIFIED: 10.0 | CLAIMED:  5.0 | UNKNOWN: 0.0
      5. Data Sensitivity:            VERIFIED: 10.0 | CLAIMED:  5.0 | UNKNOWN: 0.0
      6. ActTrident Relevance:        VERIFIED: 10.0 | CLAIMED:  5.0 | UNKNOWN: 0.0
      7. Accessible Contact:          VERIFIED: 15.0 | CLAIMED:  7.5 | UNKNOWN: 0.0
    Total possible: 100.0 pts (VERIFIED) | 50.0 pts (CLAIMED) | 0.0 pts (UNKNOWN)
    """
    factors: List[QualificationFactorResult] = []
    total_score = 0.0

    primary_source = item.website or item.source_url or "Discovery Source"

    # Factor 1: Is the company technology-related? (Max 20.0%)
    ind_str = (item.industry or "").lower()
    desc_str = (item.description or "").lower()
    name_str = (item.name or "").lower()
    is_tech_ind = any(t in ind_str for t in TECH_INDUSTRIES)
    is_tech_desc = any(t in desc_str or t in name_str for t in TECH_INDUSTRIES)
    if is_tech_ind:
        f1_state = "VERIFIED"
        f1_score = 20.0
        f1_ev = f"Industry '{item.industry}' strictly verified in technology sector"
        f1_conf = 0.95
    elif is_tech_desc:
        f1_state = "CLAIMED"
        f1_score = 10.0
        f1_ev = f"Technology references found in profile/name ('{item.name}'), industry general"
        f1_conf = 0.70
    else:
        f1_state = "UNKNOWN"
        f1_score = 0.0
        f1_ev = f"Industry '{item.industry or 'Unspecified'}' is non-technical or general"
        f1_conf = 0.50

    total_score += f1_score
    factors.append(QualificationFactorResult(
        factor_name="Is the company technology-related?",
        passed=f1_state != "UNKNOWN",
        score_weight=f1_score,
        evidence=f1_ev,
        evidence_source=primary_source,
        verification_state=f1_state,
        confidence=f1_conf,
        explanation="ActTrident workspace security solutions specifically protect developers, IT staff, and digital operators handling code and cloud infrastructure."
    ))

    # Factor 2: Does it employ at least five people? (Max 15.0%)
    emp_min = item.employee_count_min or 0
    emp_max = item.employee_count_max or 0
    has_5_emp = (emp_min >= 5) or (emp_max >= 5)
    has_emp_evidence = bool(item.employee_size_evidence and "unknown" not in item.employee_size_evidence.lower())
    if has_5_emp and has_emp_evidence:
        f2_state = "VERIFIED"
        f2_score = 15.0
        f2_ev = f"Documented workforce evidence: {item.employee_size_evidence} ({emp_min}-{emp_max} staff)"
        f2_conf = 0.90
    elif has_5_emp:
        f2_state = "CLAIMED"
        f2_score = 7.5
        f2_ev = f"Claimed {emp_min}-{emp_max} employees without corroborating official filing"
        f2_conf = 0.50
    else:
        f2_state = "UNKNOWN"
        f2_score = 0.0
        f2_ev = "Workforce size unknown or under 5 employees"
        f2_conf = 0.40

    total_score += f2_score
    factors.append(QualificationFactorResult(
        factor_name="Does it employ at least five people?",
        passed=f2_state != "UNKNOWN",
        score_weight=f2_score,
        evidence=f2_ev,
        evidence_source=primary_source,
        verification_state=f2_state,
        confidence=f2_conf,
        explanation="Separated from laptop fleet evidence. Minimum headcount confirms operational viability for team-based product trials."
    ))

    # Factor 3: Evidence of company-managed laptops? (Max 20.0%) - STRICT TRUTHFULNESS
    has_laptop_verified = bool(
        item.laptop_count_verified and
        item.laptop_count_verified >= 5 and
        item.laptop_count_evidence and
        "unknown" not in item.laptop_count_evidence.lower() and
        item.laptop_fleet_status == "VERIFIED"
    )
    has_laptop_claimed = bool(
        item.laptop_count_verified and
        item.laptop_count_verified >= 5 and
        (item.laptop_fleet_status == "CLAIMED" or not has_laptop_verified)
    )
    if has_laptop_verified:
        f3_state = "VERIFIED"
        f3_score = 20.0
        f3_ev = f"Verified {item.laptop_count_verified} laptops: {item.laptop_count_evidence}"
        f3_conf = 0.95
        f3_expl = "Documented proof confirms 5+ active company-managed devices eligible for ActTrident workspace protection."
    elif has_laptop_claimed:
        f3_state = "CLAIMED"
        f3_score = 10.0
        f3_ev = f"Claimed {item.laptop_count_verified} laptops ({item.laptop_count_evidence or 'unverified source'})"
        f3_conf = 0.45
        f3_expl = "Under ActTrident truthfulness policy, claimed device counts receive partial qualification pending corporate corroboration."
    else:
        f3_state = "UNKNOWN"
        f3_score = 0.0
        f3_ev = "No documented evidence of 5+ company-managed laptops"
        f3_conf = 0.30
        f3_expl = "Fleet evidence unknown or under 5 laptops."

    total_score += f3_score
    factors.append(QualificationFactorResult(
        factor_name="Is there evidence of company-managed laptops?",
        passed=f3_state != "UNKNOWN",
        score_weight=f3_score,
        evidence=f3_ev,
        evidence_source=primary_source,
        verification_state=f3_state,
        confidence=f3_conf,
        explanation=f3_expl
    ))

    # Factor 4: Does it use browser-based workflows? (Max 10.0%)
    BROWSER_CORE_KEYWORDS = ["saas", "cloud", "portal", "web application", "crm", "dashboard", "developer", "development", "platform", "web-based", "software", "digital", "infotech"]
    BROWSER_GENERAL_KEYWORDS = ["online", "tech", "computers", "it services", "workflows"]
    has_core_browser = any(k in desc_str or k in ind_str for k in BROWSER_CORE_KEYWORDS)
    has_general_browser = any(k in desc_str or k in ind_str or k in name_str for k in BROWSER_GENERAL_KEYWORDS)
    if bool(item.website) and (has_core_browser or any(k in desc_str for k in ["saas", "cloud", "portal", "web", "platform"])):
        f4_state = "VERIFIED"
        f4_score = 10.0
        f4_ev = "Active web domain with verified SaaS/cloud/web application workflow profile"
        f4_conf = 0.90
    elif has_core_browser or has_general_browser:
        f4_state = "CLAIMED"
        f4_score = 5.0
        f4_ev = "Web presence and commercial digital profile indicate browser-based operational workflows"
        f4_conf = 0.70
    else:
        f4_state = "UNKNOWN"
        f4_score = 0.0
        f4_ev = "No verifiable browser-based or web workflow evidence"
        f4_conf = 0.40

    total_score += f4_score
    factors.append(QualificationFactorResult(
        factor_name="Does it use browser-based workflows?",
        passed=f4_state != "UNKNOWN",
        score_weight=f4_score,
        evidence=f4_ev,
        evidence_source=item.website or "Domain DNS records",
        verification_state=f4_state,
        confidence=f4_conf,
        explanation="Browser workspace isolation delivers immediate security against web-borne data exfiltration."
    ))

    # Factor 5: Does it handle customer or business information? (Max 10.0%)
    DATA_CORE_KEYWORDS = ["client", "customer", "bpo", "financial", "database", "analytics", "patient", "user", "confidential", "deliverables", "software", "development", "it services"]
    DATA_GENERAL_KEYWORDS = ["infotech", "technology", "enterprise", "solutions", "digital"]
    has_core_data = any(k in desc_str or k in ind_str for k in DATA_CORE_KEYWORDS)
    has_gen_data = any(k in desc_str or k in ind_str or k in name_str for k in DATA_GENERAL_KEYWORDS)
    if has_core_data:
        f5_state = "VERIFIED"
        f5_score = 10.0
        f5_ev = "Business model explicitly processes client deliverables, project files, and customer account credentials"
        f5_conf = 0.90
    elif has_gen_data:
        f5_state = "CLAIMED"
        f5_score = 5.0
        f5_ev = "Technology/service business operations require handling proprietary client and operational data"
        f5_conf = 0.70
    else:
        f5_state = "UNKNOWN"
        f5_score = 0.0
        f5_ev = "Data sensitivity and client information workflows not established"
        f5_conf = 0.40

    total_score += f5_score
    factors.append(QualificationFactorResult(
        factor_name="Does it handle customer or business information?",
        passed=f5_state != "UNKNOWN",
        score_weight=f5_score,
        evidence=f5_ev,
        evidence_source=item.website or "Public business description",
        verification_state=f5_state,
        confidence=f5_conf,
        explanation="Client confidentiality obligations make compliance and data security a high executive priority."
    ))

    # Factor 6: Does its business model make ActTrident relevant? (Max 10.0%)
    if f1_state == "VERIFIED" and (has_laptop_verified or (has_5_emp and has_emp_evidence)):
        f6_state = "VERIFIED"
        f6_score = 10.0
        f6_ev = "High fit for ActTrident workspace protection and managed laptop fleet oversight"
        f6_conf = 0.90
    elif f1_state in ("VERIFIED", "CLAIMED") and (has_laptop_claimed or has_5_emp or has_core_browser or has_gen_data):
        f6_state = "CLAIMED"
        f6_score = 5.0
        f6_ev = "Relevant business model for browser workspace security; full device fleet corroboration pending"
        f6_conf = 0.65
    else:
        f6_state = "UNKNOWN"
        f6_score = 0.0
        f6_ev = "Secondary fit pending verification of commercial technology operations"
        f6_conf = 0.40

    total_score += f6_score
    factors.append(QualificationFactorResult(
        factor_name="Does its business model make ActTrident relevant?",
        passed=f6_state != "UNKNOWN",
        score_weight=f6_score,
        evidence=f6_ev,
        evidence_source="ActTrident Target Market Heuristic",
        verification_state=f6_state,
        confidence=f6_conf,
        explanation="Focuses outreach resources exclusively on prospects where ActTrident provides tangible ROI."
    ))

    # Factor 7: Is there an accessible business contact channel? (Max 15.0%)
    has_email = bool(item.public_email)
    has_phone = bool(item.public_phone or item.public_whatsapp)
    if has_email:
        f7_state = "VERIFIED"
        f7_score = 15.0
        f7_ev = f"Verified public email: {item.public_email}" + (f", Phone: {item.public_phone}" if item.public_phone else "")
        f7_conf = 0.95
    elif has_phone:
        f7_state = "CLAIMED"
        f7_score = 7.5
        f7_ev = f"Telephone/WhatsApp verified: {item.public_phone or item.public_whatsapp} (Direct email pending)"
        f7_conf = 0.70
    else:
        f7_state = "UNKNOWN"
        f7_score = 0.0
        f7_ev = "No public business contact channel verified"
        f7_conf = 0.0

    total_score += f7_score
    factors.append(QualificationFactorResult(
        factor_name="Is there an accessible business contact channel?",
        passed=f7_state != "UNKNOWN",
        score_weight=f7_score,
        evidence=f7_ev,
        evidence_source=primary_source,
        verification_state=f7_state,
        confidence=f7_conf,
        explanation="Outreach requires an authenticated, non-private business email or WhatsApp channel."
    ))

    # Determine status & reason based on canonical thresholds (High: 80-100, Medium: 60-79, Low: <60)
    total_score = round(total_score, 1)
    if total_score >= 80.0:
        if has_laptop_verified:
            cat_status = "High priority"
            cat_reason = f"Excellent candidate for ActTrident workspace protection (Score: {total_score}/100): verified {item.laptop_count_verified} managed laptops, tech sector, accessible contact."
        else:
            cat_status = "High priority"
            cat_reason = f"Strong prospect meeting core qualification criteria (Score: {total_score}/100): tech sector with documented operational signals."
    elif total_score >= 60.0:
        if not has_laptop_verified:
            cat_status = "Needs manual verification"
            cat_reason = f"Viable candidate (Score: {total_score}/100): matches technology criteria, but managed laptop count (5+) requires manual confirmation."
        else:
            cat_status = "Medium priority"
            cat_reason = f"Moderate fit (Score: {total_score}/100): meets core technology and device criteria."
    elif total_score >= 40.0:
        cat_status = "Low priority"
        cat_reason = f"Limited technology fit or insufficient contact channels available (Score: {total_score}/100)."
    else:
        cat_status = "Not suitable"
        cat_reason = f"Does not align with ActTrident target criteria for managed laptop deployments (Score: {total_score}/100)."

    return total_score, cat_status, cat_reason, factors


def qualify_company(db: Session, company: Company) -> QualificationResult:
    factors: List[QualificationFactorResult] = []
    total_score = 0.0

    # Primary source reference
    primary_source = company.sources[0].source_url if (company.sources and len(company.sources) > 0) else (company.website or "Direct verification")

    # Factor 1: Is the company technology-related? (Max 20.0%)
    industry_str = (company.industry or "").lower()
    desc_str = (company.description or "").lower()
    name_str = (company.name or "").lower()
    is_tech_ind = any(t in industry_str for t in TECH_INDUSTRIES)
    is_tech_desc = any(t in desc_str or t in name_str for t in TECH_INDUSTRIES)
    if is_tech_ind:
        f1_state = "VERIFIED"
        f1_score = 20.0
        f1_ev = f"Industry '{company.industry}' strictly verified in technology sector"
        f1_conf = 0.95
    elif is_tech_desc:
        f1_state = "CLAIMED"
        f1_score = 10.0
        f1_ev = f"Technology references found in profile/name ('{company.name}'), industry general"
        f1_conf = 0.70
    else:
        f1_state = "UNKNOWN"
        f1_score = 0.0
        f1_ev = f"Industry '{company.industry or 'Unspecified'}' is non-technical or general"
        f1_conf = 0.50

    total_score += f1_score
    factors.append(QualificationFactorResult(
        factor_name="Is the company technology-related?",
        passed=f1_state != "UNKNOWN",
        score_weight=f1_score,
        evidence=f1_ev,
        evidence_source=company.website or "Company Registry / MSME Profile",
        verification_state=f1_state,
        confidence=f1_conf,
        explanation="ActTrident workspace security solutions specifically protect developers, IT staff, and digital operators handling code and cloud infrastructure."
    ))

    # Factor 2: Does it employ at least five people? (Max 15.0%)
    emp_min = company.employee_count_min or 0
    emp_max = company.employee_count_max or 0
    has_5_emp = (emp_min >= 5) or (emp_max >= 5)
    has_emp_evidence = bool(company.employee_size_evidence and "unknown" not in company.employee_size_evidence.lower())
    if has_5_emp and has_emp_evidence:
        f2_state = "VERIFIED"
        f2_score = 15.0
        f2_ev = f"Documented workforce evidence: {company.employee_size_evidence} ({emp_min}-{emp_max} staff)"
        f2_conf = 0.90
    elif has_5_emp:
        f2_state = "CLAIMED"
        f2_score = 7.5
        f2_ev = f"Claimed {emp_min}-{emp_max} employees without corroborating official filing"
        f2_conf = 0.50
    else:
        f2_state = "UNKNOWN"
        f2_score = 0.0
        f2_ev = "Workforce size unknown or under 5 employees"
        f2_conf = 0.40

    total_score += f2_score
    factors.append(QualificationFactorResult(
        factor_name="Does it employ at least five people?",
        passed=f2_state != "UNKNOWN",
        score_weight=f2_score,
        evidence=f2_ev,
        evidence_source=primary_source,
        verification_state=f2_state,
        confidence=f2_conf,
        explanation="Separated from laptop fleet evidence. Minimum headcount confirms operational viability for team-based product trials."
    ))

    # Factor 3: Is there evidence of company-managed laptops? (Max 20.0%) - STRICT TRUTHFULNESS
    fleet_st = getattr(company, "laptop_fleet_status", "UNKNOWN")
    has_laptop_verified = bool(
        company.laptop_count_verified and
        company.laptop_count_verified >= 5 and
        company.laptop_count_evidence and
        "unknown" not in company.laptop_count_evidence.lower() and
        (fleet_st == "VERIFIED" or len(company.laptop_count_evidence.strip()) >= 10)
    )
    has_laptop_claimed = bool(
        company.laptop_count_verified and
        company.laptop_count_verified >= 5 and
        not has_laptop_verified
    )
    has_laptop_evidence = has_laptop_verified
    if has_laptop_verified:
        f3_state = "VERIFIED"
        f3_score = 20.0
        f3_ev = f"Verified {company.laptop_count_verified} laptops: {company.laptop_count_evidence}"
        f3_conf = 0.95
        f3_expl = "Documented proof confirms 5+ active company-managed devices eligible for ActTrident workspace protection."
    elif has_laptop_claimed:
        f3_state = "CLAIMED"
        f3_score = 10.0
        f3_ev = f"Claimed {company.laptop_count_verified} laptops ({company.laptop_count_evidence or 'unverified source'})"
        f3_conf = 0.45
        f3_expl = "Under ActTrident truthfulness policy, claimed device counts receive partial qualification pending corporate corroboration."
    else:
        f3_state = "UNKNOWN"
        f3_score = 0.0
        f3_ev = "No documented evidence of 5+ company-managed laptops"
        f3_conf = 0.30
        f3_expl = "Fleet evidence unknown or under 5 laptops."

    total_score += f3_score
    factors.append(QualificationFactorResult(
        factor_name="Is there evidence of company-managed laptops?",
        passed=f3_state != "UNKNOWN",
        score_weight=f3_score,
        evidence=f3_ev,
        evidence_source=primary_source,
        verification_state=f3_state,
        confidence=f3_conf,
        explanation=f3_expl
    ))

    # Factor 4: Does it use browser-based workflows? (Max 10.0%)
    BROWSER_CORE_KEYWORDS = ["saas", "cloud", "portal", "web application", "crm", "dashboard", "developer", "development", "platform", "web-based", "software", "digital", "infotech"]
    BROWSER_GENERAL_KEYWORDS = ["online", "tech", "computers", "it services", "workflows"]
    has_core_browser = any(k in desc_str or k in industry_str for k in BROWSER_CORE_KEYWORDS)
    has_general_browser = any(k in desc_str or k in industry_str or k in name_str for k in BROWSER_GENERAL_KEYWORDS)
    if bool(company.website) and (has_core_browser or any(k in desc_str for k in ["saas", "cloud", "portal", "web", "platform"])):
        f4_state = "VERIFIED"
        f4_score = 10.0
        f4_ev = "Active web domain with verified SaaS/cloud/web application workflow profile"
        f4_conf = 0.90
    elif has_core_browser or has_general_browser:
        f4_state = "CLAIMED"
        f4_score = 5.0
        f4_ev = "Web presence and commercial digital profile indicate browser-based operational workflows"
        f4_conf = 0.70
    else:
        f4_state = "UNKNOWN"
        f4_score = 0.0
        f4_ev = "No verifiable browser-based or web workflow evidence"
        f4_conf = 0.40

    total_score += f4_score
    factors.append(QualificationFactorResult(
        factor_name="Does it use browser-based workflows?",
        passed=f4_state != "UNKNOWN",
        score_weight=f4_score,
        evidence=f4_ev,
        evidence_source=company.website or "Domain DNS records",
        verification_state=f4_state,
        confidence=f4_conf,
        explanation="Browser workspace isolation delivers immediate security against web-borne data exfiltration."
    ))

    # Factor 5: Does it handle customer or business information? (Max 10.0%)
    DATA_CORE_KEYWORDS = ["client", "customer", "bpo", "financial", "database", "analytics", "patient", "user", "confidential", "deliverables", "software", "development", "it services"]
    DATA_GENERAL_KEYWORDS = ["infotech", "technology", "enterprise", "solutions", "digital"]
    has_core_data = any(k in desc_str or k in industry_str for k in DATA_CORE_KEYWORDS)
    has_gen_data = any(k in desc_str or k in industry_str or k in name_str for k in DATA_GENERAL_KEYWORDS)
    if has_core_data:
        f5_state = "VERIFIED"
        f5_score = 10.0
        f5_ev = "Business model explicitly processes client deliverables, project files, and customer account credentials"
        f5_conf = 0.90
    elif has_gen_data:
        f5_state = "CLAIMED"
        f5_score = 5.0
        f5_ev = "Technology/service business operations require handling proprietary client and operational data"
        f5_conf = 0.70
    else:
        f5_state = "UNKNOWN"
        f5_score = 0.0
        f5_ev = "Data sensitivity and client information workflows not established"
        f5_conf = 0.40

    total_score += f5_score
    factors.append(QualificationFactorResult(
        factor_name="Does it handle customer or business information?",
        passed=f5_state != "UNKNOWN",
        score_weight=f5_score,
        evidence=f5_ev,
        evidence_source=company.website or "Public business description",
        verification_state=f5_state,
        confidence=f5_conf,
        explanation="Client confidentiality obligations make compliance and data security a high executive priority."
    ))

    # Factor 6: Does its business model make ActTrident relevant? (Max 10.0%)
    if f1_state == "VERIFIED" and (has_laptop_verified or (has_5_emp and has_emp_evidence)):
        f6_state = "VERIFIED"
        f6_score = 10.0
        f6_ev = "High fit for ActTrident workspace protection and managed laptop fleet oversight"
        f6_conf = 0.90
    elif f1_state in ("VERIFIED", "CLAIMED") and (has_laptop_claimed or has_5_emp or has_core_browser or has_gen_data):
        f6_state = "CLAIMED"
        f6_score = 5.0
        f6_ev = "Relevant business model for browser workspace security; full device fleet corroboration pending"
        f6_conf = 0.65
    else:
        f6_state = "UNKNOWN"
        f6_score = 0.0
        f6_ev = "Secondary fit pending verification of commercial technology operations"
        f6_conf = 0.40

    total_score += f6_score
    factors.append(QualificationFactorResult(
        factor_name="Does its business model make ActTrident relevant?",
        passed=f6_state != "UNKNOWN",
        score_weight=f6_score,
        evidence=f6_ev,
        evidence_source="ActTrident Target Market Heuristic",
        verification_state=f6_state,
        confidence=f6_conf,
        explanation="Focuses outreach resources exclusively on prospects where ActTrident provides tangible ROI."
    ))

    # Factor 7: Is there an accessible business contact channel? (Max 15.0%)
    has_email = bool(company.public_email or company.decision_maker_email)
    has_phone = bool(company.public_phone or company.public_whatsapp)
    if has_email:
        f7_state = "VERIFIED"
        f7_score = 15.0
        f7_ev = f"Verified public email: {company.public_email or company.decision_maker_email}" + (f", Phone: {company.public_phone}" if company.public_phone else "")
        f7_conf = 0.95
    elif has_phone:
        f7_state = "CLAIMED"
        f7_score = 7.5
        f7_ev = f"Telephone/WhatsApp verified: {company.public_phone or company.public_whatsapp} (Direct email pending)"
        f7_conf = 0.70
    else:
        f7_state = "UNKNOWN"
        f7_score = 0.0
        f7_ev = "No public business contact channel verified"
        f7_conf = 0.0

    total_score += f7_score
    factors.append(QualificationFactorResult(
        factor_name="Is there an accessible business contact channel?",
        passed=f7_state != "UNKNOWN",
        score_weight=f7_score,
        evidence=f7_ev,
        evidence_source=primary_source,
        verification_state=f7_state,
        confidence=f7_conf,
        explanation="Outreach requires an authenticated, non-private business email or WhatsApp channel."
    ))

    # Determine Classification Status & Recommended Next Action based on canonical thresholds (High: 80-100, Medium: 60-79, Low: <60)
    total_score = round(total_score, 1)
    if total_score >= 80.0:
        if has_laptop_verified:
            status = "High priority"
            reason = f"Excellent candidate for ActTrident workspace protection (Score: {total_score}/100): verified {company.laptop_count_verified} managed laptops, tech sector, accessible contact."
            action = "Generate AI email draft and route to manager approval queue for evaluation invitation."
        else:
            status = "High priority"
            reason = f"Strong prospect meeting core qualification criteria (Score: {total_score}/100): tech sector with documented operational signals."
            action = "Generate introductory AI email draft and route to approval queue."
    elif total_score >= 60.0:
        if not has_laptop_verified:
            status = "Needs manual verification"
            reason = f"Viable candidate (Score: {total_score}/100): matches technology criteria, but managed laptop count (5+) requires manual confirmation."
            action = "Dispatch research specialist to review careers page, MCA filings, or LinkedIn office tours for fleet evidence."
        else:
            status = "Medium priority"
            reason = f"Moderate fit (Score: {total_score}/100): meets core technology and device criteria."
            action = "Draft introductory outreach proposing preliminary capabilities review."
    elif total_score >= 40.0:
        status = "Low priority"
        reason = f"Limited technology fit or insufficient contact channels available (Score: {total_score}/100)."
        action = "Monitor for future expansion or secondary outreach cycle."
    else:
        status = "Not suitable"
        reason = "Does not align with ActTrident target criteria for managed laptop deployments."
        action = "Archive lead record to suppression list."

    # Check suppression registry
    from app.models.activity import SuppressionList
    from urllib.parse import urlparse
    suppressed = False
    clean_email = (company.public_email or "").strip().lower()
    if clean_email:
        supp = db.query(SuppressionList).filter(SuppressionList.identifier == clean_email).first()
        if supp:
            suppressed = True
    if company.website and not suppressed:
        host = urlparse(company.website).hostname or ""
        clean_host = host.replace("www.", "").strip().lower()
        if clean_host:
            supp = db.query(SuppressionList).filter(SuppressionList.identifier == clean_host).first()
            if supp:
                suppressed = True

    if suppressed:
        status = "Unqualified"
        reason = "Lead contact or web domain is registered on the suppression / opt-out list."
        action = "Do not contact. Administratively suppressed."

    # Intelligent Service Matching
    from app.services.service_catalogue_service import match_service_for_company
    svc_match = match_service_for_company(company, db=db)
    matched_svc_id = svc_match.service_id if svc_match else None
    matched_svc_name = svc_match.service_name if svc_match else None
    matched_svc_rationale = svc_match.rationale if svc_match else None

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
        matched_service_id=matched_svc_id,
        matched_service_name=matched_svc_name,
        matched_service_rationale=matched_svc_rationale,
        website_classification=getattr(company, "website_classification", "unverified"),
        email_verification_status=getattr(company, "email_verification_status", "unknown"),
        phone_verification_status=getattr(company, "phone_verification_status", "unknown"),
        last_verified_at=now_utc,
        is_stale=False
    )

    # Persist in Company record
    company.qualification_score = result.score
    company.qualification_status = result.status
    company.qualification_reason = result.reason
    company.qualification_factors = json.dumps([f.model_dump() for f in factors])
    company.has_verified_5_plus_laptops = has_laptop_evidence
    company.matched_service_id = matched_svc_id
    company.matched_service_name = matched_svc_name
    company.matched_service_rationale = matched_svc_rationale
    company.date_last_verified = now_utc

    # If lead exists, update pipeline status
    if company.lead:
        if status in ["High priority", "Medium priority"]:
            company.lead.pipeline_status = "qualified"
        elif status == "Needs manual verification":
            company.lead.pipeline_status = "researching"
        elif status == "Unqualified":
            company.lead.pipeline_status = "do_not_contact"

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
