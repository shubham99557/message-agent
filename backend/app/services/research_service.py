import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
import httpx

from app.models.company import Company
from app.models.research import ResearchReport
from app.schemas.research import DiscoveredCompanyItem
from app.core.security import is_safe_external_url, sanitize_untrusted_text, safe_fetch_untrusted_url
from app.integrations.discovery_adapters import is_demo_domain

logger = logging.getLogger("acttrident.research")


def _strip_html_to_text(raw_html: str) -> str:
    """Removes script/style blocks and HTML tags from untrusted web content."""
    cleaned = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw_html)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


async def fetch_website_content_safely(url: str) -> Optional[str]:
    """
    Safely retrieves public web content while blocking SSRF to private/internal IPs,
    revalidating redirect hops, and preventing memory exhaustion.
    """
    if not url or is_demo_domain(url) or not is_safe_external_url(url):
        return None
    try:
        success, text, final_url, err = await safe_fetch_untrusted_url(
            url,
            max_bytes=20000,
            timeout_seconds=8.0,
            max_redirects=3
        )
        if success and text:
            cleaned = _strip_html_to_text(text)
            return sanitize_untrusted_text(cleaned[:2000])
    except Exception:
        return None
    return None


def _assess_evidence_and_gaps(
    company: Company,
    website_fetched: bool,
) -> Tuple[List[str], float]:
    """
    Produces an explicit list of missing/unverified facts and an honest evidence confidence score (0.0-1.0).
    Never invents facts to fill gaps.
    """
    missing: List[str] = []

    if company.is_demo or company.verification_status == "demo_fixture" or is_demo_domain(company.website):
        missing.append("Demo fixture record — not a verified real prospect; do not send real outreach.")
        return missing, 0.0

    confidence = 0.0

    if company.website:
        confidence += 0.15
        if website_fetched:
            confidence += 0.15
        else:
            missing.append("Public website could not be retrieved or verified during this research run.")
    else:
        missing.append("Official company website URL is missing.")

    if company.public_email or company.public_phone or company.public_whatsapp:
        confidence += 0.15
    if not company.public_email:
        missing.append("Public business email address is not verified.")
    if not (company.public_phone or company.public_whatsapp):
        missing.append("Public business phone / WhatsApp number is not verified.")

    if company.sources and len(company.sources) > 0:
        confidence += 0.15
    else:
        missing.append("No traceable external ContactSource provenance records attached yet.")

    if company.employee_count_min or company.employee_count_max or company.employee_size_evidence:
        confidence += 0.10
    else:
        missing.append("Employee headcount and supporting evidence are unknown.")

    if company.laptop_count_verified and company.laptop_count_verified >= 5 and company.laptop_count_evidence:
        confidence += 0.20
    else:
        missing.append("Managed company laptop fleet (5+ devices) is Unknown / not verified with documented evidence.")

    if not company.decision_maker_name and not company.decision_maker_role:
        missing.append("Relevant decision-maker name and role are not publicly verified.")

    if company.verification_status == "verified":
        confidence += 0.10
    else:
        missing.append(f"Company record status is '{company.verification_status or 'unverified'}' (requires human verification before live outreach).")

    return missing, round(min(confidence, 1.0), 2)


async def generate_research_dossier_for_item(item: DiscoveredCompanyItem) -> Dict[str, Any]:
    """
    Generates a structured 13-dimension research dossier for a DiscoveredCompanyItem using local Ollama.
    Handles Ollama unavailability honestly, produces schema-validated JSON, and records missing information.
    """
    website_content: Optional[str] = None
    if item.website and not item.is_demo and is_safe_external_url(item.website):
        website_content = await fetch_website_content_safely(item.website)

    missing_items: List[str] = []
    if not item.website:
        missing_items.append("Official company website URL is missing")
    elif not website_content:
        missing_items.append("Public website could not be retrieved during research run")
    if not item.public_email:
        missing_items.append("Public business email address is not verified")
    if not (item.public_phone or item.public_whatsapp):
        missing_items.append("Public business telephone/WhatsApp number is not verified")
    if not (item.employee_count_min or item.employee_count_max):
        missing_items.append("Employee headcount evidence is unknown")
    if not (item.laptop_count_verified and item.laptop_fleet_status == "VERIFIED"):
        missing_items.append("Company-managed laptop fleet (5+ devices) is Unknown / unverified")
    if not item.decision_maker_name:
        missing_items.append("Decision-maker identity is not publicly confirmed")

    missing_str = "; ".join(missing_items) if missing_items else "None — all core qualification fields verified"

    dossier: Dict[str, Any] = {
        "company_overview": f"{item.name} is a commercial entity in {item.city}, {item.state or 'India'}, categorized under '{item.industry or 'Technology Services'}'.",
        "main_services": item.description or f"Services related to {item.industry or 'Business & Technology'}",
        "industry": item.industry or "Technology Services",
        "business_location": f"{item.city}, {item.state or 'India'}",
        "publicly_available_company_size": (
            f"{item.employee_count_min}-{item.employee_count_max} employees" if (item.employee_count_min and item.employee_count_max)
            else (f"{item.employee_count_min}+ employees" if item.employee_count_min else "Unknown — pending verification")
        ),
        "operational_characteristics": f"Operations in {item.city}. Website status: {item.website_status or 'unverified'}.",
        "potential_acttrident_use_cases": "Centralized endpoint visibility, browser workspace isolation, and SaaS account data protection.",
        "potential_security_challenges": "[Inferred hypothesis] Potential web-borne exfiltration risks and browser credential exposure during distributed operations.",
        "possible_decision_maker_roles": item.decision_maker_role or "Managing Director / CTO / Head of Engineering / IT Lead",
        "available_contact_channels": ", ".join([c for c in [item.public_email, item.public_phone, item.public_whatsapp] if c]) or "None verified",
        "evidence_backed_qualification_explanation": f"Evaluation based on industry '{item.industry}', city '{item.city}', and contact channel availability.",
        "missing_information": missing_str,
        "recommended_next_research_step": "Confirm managed laptop count (5+) and establish authenticated contact via official email.",
        "ai_status": "completed",
    }

    try:
        from app.ai.local_ai_gateway import local_ai_gateway
        comp_payload = {
            "name": item.name,
            "website": item.website,
            "industry": item.industry,
            "city": item.city,
            "state": item.state,
            "laptop_count_verified": item.laptop_count_verified,
            "laptop_count_evidence": item.laptop_count_evidence,
            "decision_maker_name": item.decision_maker_name,
            "decision_maker_role": item.decision_maker_role,
        }
        res_dossier = await local_ai_gateway.generate_research_dossier(comp_payload, web_content=website_content or "")
        if res_dossier and res_dossier.summary and len(res_dossier.summary) > 20:
            dossier["company_overview"] = res_dossier.summary
        if res_dossier and res_dossier.products_and_services:
            dossier["main_services"] = res_dossier.products_and_services
        if res_dossier and getattr(res_dossier, "it_pain_points", None):
            dossier["potential_security_challenges"] = f"[Hypothesis] {res_dossier.it_pain_points}"
        if getattr(local_ai_gateway, "active_provider", "") == "deterministic":
            dossier["ai_status"] = "ai_unavailable"
    except Exception as exc:
        logger.debug(f"AI dossier generation for item skipped/failed: {exc}")
        dossier["ai_status"] = "ai_unavailable"

    return dossier


async def generate_company_research_report(db: Session, company: Company) -> ResearchReport:
    """
    Generates a truthful, source-attributed research report.
    Strictly separates verified facts from inferred recommendations and explicitly lists missing information.
    Never fabricates cyberattacks, employee counts, laptop counts, or decision-maker identities.
    """
    website_content: Optional[str] = None
    if company.website and not company.is_demo and is_safe_external_url(company.website):
        website_content = await fetch_website_content_safely(company.website)

    missing_items, confidence_level = _assess_evidence_and_gaps(company, website_fetched=bool(website_content))
    missing_information_str = "; ".join(missing_items) if missing_items else "None — all core qualification fields have documented evidence."

    # Build strictly truthful summary without inventing employee numbers
    if company.employee_count_min and company.employee_count_max:
        workforce_clause = f"a documented workforce estimate of {company.employee_count_min}-{company.employee_count_max} personnel"
    elif company.employee_count_min:
        workforce_clause = f"an estimated minimum workforce of {company.employee_count_min} personnel"
    elif company.employee_count_max:
        workforce_clause = f"an estimated workforce up to {company.employee_count_max} personnel"
    else:
        workforce_clause = "an unverified workforce size (Unknown)"

    demo_prefix = "[DEMO FIXTURE — NOT A REAL PROSPECT] " if (company.is_demo or company.verification_status == "demo_fixture") else ""
    summary = (
        f"{demo_prefix}{company.name} is recorded in {company.city}"
        f"{f', {company.state}' if company.state else ''}, "
        f"under industry '{company.industry or 'Unspecified'}', with {workforce_clause}. "
        f"Record verification status: {company.verification_status or 'unverified'}."
    )
    services = (
        company.description
        if company.description
        else f"Recorded industry sector: {company.industry or 'Unspecified'}. Specific service catalog not yet verified from public sources."
    )

    if website_content:
        snippet = website_content[:260].strip()
        summary += f" Public website excerpt (untrusted source): \"{snippet}\""

    try:
        from app.ai.local_ai_gateway import local_ai_gateway
        comp_payload = {
            "name": company.name,
            "website": company.website,
            "industry": company.industry,
            "city": company.city,
            "state": company.state,
            "laptop_count_verified": company.laptop_count_verified,
            "laptop_count_evidence": company.laptop_count_evidence,
            "decision_maker_name": company.decision_maker_name,
            "decision_maker_role": company.decision_maker_role,
        }
        dossier = await local_ai_gateway.generate_research_dossier(comp_payload, web_content=website_content or "")
        if dossier and dossier.summary and len(dossier.summary) > 20:
            status_tag = f"Record status: {company.verification_status or 'unverified'}."
            summary = f"{demo_prefix}{dossier.summary} [{status_tag}] [Local AI: {local_ai_gateway.model_manager.active_model}]"
        if dossier and dossier.products_and_services:
            services = dossier.products_and_services
    except Exception as exc:
        logger.debug(f"Local AI dossier synthesis notice: {exc}")

    if company.laptop_count_verified and company.laptop_count_evidence:
        laptop_clause = f"{company.laptop_count_verified} verified company-managed workstations ({company.laptop_count_evidence})"
    else:
        laptop_clause = "an unverified workstation count (Unknown — requires confirmation of 5+ managed laptops)"

    likely_tech = (
        f"[Inferred hypothesis, not verified fact] Organization may use standard business cloud tools and {laptop_clause} "
        f"that could benefit from centralized endpoint visibility and secure browser workspace isolation."
    )

    use_cases = (
        "1. Endpoint posture monitoring and managed laptop oversight (subject to confirming 5+ company laptops).\n"
        "2. Secure browser workspace isolation for business web workflows and client data handling.\n"
        "3. Proposed ActTrident 90-day free product evaluation for qualified teams."
    )

    if company.decision_maker_name and company.decision_maker_role:
        decision_maker = f"{company.decision_maker_name} ({company.decision_maker_role})"
    elif company.decision_maker_role:
        decision_maker = f"{company.decision_maker_role} (name not yet publicly verified)"
    else:
        decision_maker = "Unknown — target roles to verify: Founder / Managing Director / CTO / IT Manager"

    target_contact_ref = company.decision_maker_name or company.decision_maker_role or "the verified IT or business leader (not yet identified)"
    recommended_approach = (
        f"Verify missing evidence first ({len(missing_items)} gap(s) flagged), then approach {target_contact_ref} "
        f"via an authorized business channel with a concise introduction to the proposed ActTrident 90-day free product evaluation."
    )

    # Gather all verified / recorded source attributions
    sources_list = [
        f"{s.field_name}: {s.source_url} ({s.source_type}, status={getattr(s, 'verification_status', 'unverified')})"
        for s in (company.sources or [])
    ]
    if website_content and company.website:
        sources_list.append(f"website_snapshot: {company.website} (public_website_fetch)")
    sources_str = " | ".join(sources_list) if sources_list else (
        f"Website recorded: {company.website} (unfetched)" if company.website else "No external source URLs recorded"
    )

    # Upsert report
    report = db.query(ResearchReport).filter(ResearchReport.company_id == company.id).first()
    if not report:
        report = ResearchReport(
            company_id=company.id,
            summary=summary,
            services=services,
            likely_tech_requirements=likely_tech,
            potential_acttrident_use_cases=use_cases,
            relevant_decision_maker_role=decision_maker,
            recommended_outreach_approach=recommended_approach,
            sources_summary=sources_str,
            missing_information=missing_information_str,
            confidence_level=confidence_level,
        )
        db.add(report)
    else:
        report.summary = summary
        report.services = services
        report.likely_tech_requirements = likely_tech
        report.potential_acttrident_use_cases = use_cases
        report.relevant_decision_maker_role = decision_maker
        report.recommended_outreach_approach = recommended_approach
        report.sources_summary = sources_str
        report.missing_information = missing_information_str
        report.confidence_level = confidence_level

    db.commit()
    db.refresh(report)
    return report
