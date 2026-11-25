import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyContact, ContactSource
from app.models.campaign import Campaign
from app.models.email import EmailDraft
from app.models.research import ResearchReport
from app.models.activity import SuppressionList
from app.schemas.email import (
    EmailGenerateRequest,
    EmailVariationsRequest,
    EmailVariationsResponse,
    EmailVariationItem,
)
from app.core.config import settings
from app.core.product_claims import validate_message_against_claims
from app.core.security import validate_recipient_email_syntax
from app.core.compliance_policy_engine import CompliancePolicyEngine, PolicyViolationError
from app.services.service_catalogue_service import (
    get_service_by_id,
    get_service_by_code,
    match_service_for_company,
)
from app.ai.local_ai_gateway import local_ai_gateway

logger = logging.getLogger("acttrident.email_generator")


OPT_OUT_SENTENCE = "If you would prefer not to receive further business emails from us, please reply and let us know."

PLACEHOLDER_PATTERN = re.compile(
    r"\[(?:Your|Company|Recipient|CTA|Insert|Name|Title|Role|Email|Phone|Date|Time|Link|Button|Prospect)[^\]]*\]"
    r"|\{\{[^}]+\}\}"
    r"|\{(?:company_name|contact_name|city|industry)\}",
    re.IGNORECASE,
)


def detect_unresolved_placeholders(text: str) -> List[str]:
    """Detects any unresolved template placeholders in generated email subject or body."""
    if not text:
        return []
    return PLACEHOLDER_PATTERN.findall(text)


def ensure_opt_out_sentence(body_text: str) -> str:
    """Appends the approved reply-based opt-out sentence if missing, without fake URLs."""
    clean = (body_text or "").strip()
    if "prefer not to receive" in clean.lower() or "unsubscribe" in clean.lower() or "opt out" in clean.lower():
        return clean
    return f"{clean}\n\n---\n{OPT_OUT_SENTENCE}"


def _possessive(name: str) -> str:
    """Formats possessive company name cleanly without awkward .'s."""
    clean = (name or "your organization").strip().rstrip(".")
    if clean.endswith(("s", "S")):
        return f"{clean}'"
    return f"{clean}'s"


def _is_website_verified_accessible(company: Company, db: Optional[Session] = None) -> bool:
    """Returns True only if the company has a website that is verified/authentic, not unavailable."""
    if not company.website:
        return False
    wc = (getattr(company, "website_classification", "") or "").lower()
    if wc in ("authentic", "likely_authentic"):
        return True
    if wc in ("unavailable", "parked", "suspicious", "unrelated"):
        return False
    if db is not None:
        src = (
            db.query(ContactSource)
            .filter(ContactSource.company_id == company.id, ContactSource.field_name == "official_website")
            .order_by(ContactSource.id.desc())
            .first()
        )
        if src and (src.verification_status or "").lower() == "verified":
            return True
    return False


def _is_synthetic_fixture(company: Company) -> bool:
    """Checks whether a company record is an internal synthetic test fixture or demo seed."""
    if getattr(company, "is_demo", False):
        return True
    verif = getattr(company, "verification_status", "").lower()
    if verif in ("synthetic_fixture", "demo_fixture", "historical_test"):
        return True
    name = (getattr(company, "name", "") or "").lower()
    if "live test" in name or "audit-" in name:
        return True
    return False


def build_email_variations_deterministic(
    company: Company,
    contact: Optional[CompanyContact],
    matched_service_name: str,
    matched_service_code: str,
    tone: str = "Professional",
    custom_notes: Optional[str] = None,
    research_summary: Optional[str] = None,
    website_verified: bool = False,
) -> Tuple[List[str], Dict[str, Dict[str, str]]]:
    """
    Deterministic generation engine for Phase 3 email variations.
    Produces 3 useful variations (Short, Standard, Consultative) and 4 varied subject line suggestions.
    Guarantees strict compliance with ActTrident product claims, truthfulness, and zero-hallucination rules.
    """
    recipient_name = (contact.name if contact else None) or company.decision_maker_name or "Team"
    city = company.city or "India"
    industry = company.industry or "technology"
    has_laptops = company.has_verified_5_plus_laptops
    laptop_count = company.laptop_count_verified
    possessive_name = _possessive(company.name)

    clean_tone = tone.strip().lower()

    # 1. Subject Line Options (Strictly approved claims, no unverified capabilities)
    if matched_service_code == "ACT-WS-01":
        subjects = [
            f"ActTrident: Browser workspace & endpoint protection for {company.name}",
            f"Safeguarding proprietary code and sessions at {company.name}",
            f"Workstation & browser workspace protection for {city} teams: {company.name}",
            f"Zero-trust browser credential isolation overview for {company.name}"
        ]
    elif matched_service_code == "ACT-CL-02":
        subjects = [
            f"ActTrident: Browser credential isolation for {company.name}",
            f"Protecting cloud credentials and web sessions at {company.name}",
            f"Zero-trust browser session protection for {possessive_name} team",
            f"Workstation posture & credential isolation in {city}: {company.name}"
        ]
    elif matched_service_code == "ACT-AU-03":
        subjects = [
            f"ActTrident: Workspace protection & posture overview for {company.name}",
            f"Supporting secure digital operations at {company.name}",
            f"Workstation & browser session protection for {company.name}",
            f"Technical introduction: ActTrident & {company.name} ({city})"
        ]
    else:
        subjects = [
            f"ActTrident Technology Introduction for {company.name}",
            f"Workstation security & browser posture for {company.name}",
            f"Securing distributed operations for {company.name} in {city}",
            f"Technical introduction: ActTrident & {company.name}"
        ]

    # Greeting by Tone
    if "friendly" in clean_tone:
        greeting = f"Hi {recipient_name},"
    elif "formal" in clean_tone:
        greeting = f"Dear {recipient_name},"
    else:
        greeting = f"Hello {recipient_name},"

    # Evidence-grounded opening (never claim active footprint if website is unavailable/unverified)
    first_research_sentence = ""
    if research_summary and "could not be retrieved" not in research_summary.lower():
        first_sentence = research_summary.split(".")[0].strip()
        if first_sentence and len(first_sentence) > 20:
            first_research_sentence = f"From your public profile, we noted that {first_sentence[0].lower() + first_sentence[1:]}."

    if website_verified and first_research_sentence:
        opening_context = first_research_sentence
    elif website_verified:
        opening_context = f"We reviewed {possessive_name} public profile in {industry} in {city}."
    else:
        opening_context = f"I am reaching out from ActTrident to introduce our workstation protection platform to {company.name} in {city}."

    # --- VARIATION A: SHORT PROFESSIONAL INTRODUCTION ---
    var_a_subject = subjects[0]
    var_a_body = ensure_opt_out_sentence(
        f"{greeting}\n\n"
        f"{opening_context} ActTrident provides non-intrusive runtime workspace protection for distributed company laptops, "
        f"isolating browser workspaces and safeguarding cloud credentials against session hijacking and unauthorized copy/paste operations.\n\n"
        f"Would you be open to a brief 10-minute introductory call next Tuesday or Wednesday to see if this aligns with your priorities?\n\n"
        f"Best regards,\n"
        f"ActTrident Business Development\n"
        f"https://acttrident.ai/"
    )

    # --- VARIATION B: STANDARD PERSONALIZED BUSINESS EMAIL ---
    if has_laptops and laptop_count:
        device_note = (
            f"We understand your team manages company laptops across your operations in {city}, "
            f"where maintaining verified device posture around sensitive web sessions is an important operational priority."
        )
    else:
        device_note = (
            f"For organizations in {city} managing distributed workflows, "
            f"isolating browser workspaces and protecting corporate web credentials helps reduce everyday data-handling risk."
        )

    eval_offer = ""
    if getattr(settings, "ALLOW_90_DAY_EVALUATION_OFFER", False):
        eval_offer = " For eligible organizations with 5+ managed laptops, we also offer a 90-day free product evaluation with onboarding support."

    var_b_subject = subjects[0] if "technical" in clean_tone else subjects[1]
    var_b_body = ensure_opt_out_sentence(
        f"{greeting}\n\n"
        f"{opening_context}\n\n"
        f"{device_note}\n\n"
        f"ActTrident delivers {matched_service_name.lower()} through non-intrusive runtime workspace protection, "
        f"zero-trust browser credential isolation against malicious extensions and unauthorized copy/paste, "
        f"and centralized device posture verification.{eval_offer}\n\n"
        f"Would next Tuesday or Wednesday afternoon work for a concise 15-minute product overview?\n\n"
        f"Best regards,\n"
        f"ActTrident Business Development\n"
        f"https://acttrident.ai/"
    )

    # --- VARIATION C: DETAILED CONSULTATIVE EMAIL ---
    var_c_subject = subjects[2] if len(subjects) > 2 else subjects[0]
    var_c_body = ensure_opt_out_sentence(
        f"{greeting}\n\n"
        f"{opening_context} As {industry} teams in {city} balance productivity with client data protection, "
        f"securing browser-based workflows across distributed laptops without heavy administrative overhead is a common priority.\n\n"
        f"ActTrident focuses on three core capabilities:\n"
        f"• Runtime Workspace Protection: Isolates browser workspaces on distributed company laptops to help prevent unauthorized data exfiltration.\n"
        f"• Zero-Trust Browser Credential Isolation: Safeguards cloud credentials and sensitive web sessions against session hijacking, malicious browser extensions, and unauthorized copy/paste operations.\n"
        f"• Centralized Device Posture Verification: Continuously checks that laptops accessing company resources meet verified security health baselines.\n\n"
        f"Would you be open to a 15-minute technical exchange next week to discuss whether these controls fit {possessive_name} environment?\n\n"
        f"Warm regards,\n"
        f"ActTrident Business Development\n"
        f"https://acttrident.ai/"
    )

    variations = {
        "short": {
            "subject": var_a_subject,
            "body_text": var_a_body,
            "description": "Short Professional Introduction (3 concise paragraphs for busy decision-makers)"
        },
        "standard": {
            "subject": var_b_subject,
            "body_text": var_b_body,
            "description": "Standard Personalized Business Email (comprehensive company context & solution fit)"
        },
        "consultative": {
            "subject": var_c_subject,
            "body_text": var_c_body,
            "description": "Detailed Consultative Email (architecture, security capabilities & operational tradeoff analysis)"
        }
    }

    return subjects, variations


def build_email_content(
    company: Company,
    contact: Optional[CompanyContact],
    tone: str = "Professional",
    draft_type: str = "initial_email",
    variation_type: str = "standard",
    target_service_name: Optional[str] = None,
    service_description: Optional[str] = None,
    custom_notes: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Builds personalized email content adhering strictly to ActTrident messaging and claims boundaries.
    Supports variation types: short, standard, consultative.
    Supports tones: Professional, Friendly, Consultative, Technical.
    """
    svc_name = target_service_name or company.matched_service_name or "Secure Workspace & Endpoint Isolation"
    svc_code = getattr(company, "matched_service_code", None) or "ACT-WS-01"
    recipient_name = (contact.name if contact else None) or company.decision_maker_name or "Team"
    city = company.city or "India"

    if draft_type == "whatsapp_draft":
        subject = f"WhatsApp Intro: {company.name}"
        body_text = (
            f"Hi {recipient_name}, reaching out from ActTrident (https://acttrident.ai/) regarding {svc_name} "
            f"for {company.name} in {city}. Open to a quick 5-minute chat or sharing a brief overview?"
        )
        body_html = f"<p>{body_text}</p>"
        return subject, body_text, body_html

    if draft_type == "linkedin_message":
        subject = f"Connecting re: {svc_name} at {company.name}"
        body_text = (
            f"Hi {recipient_name}, I noticed {company.name}'s work in {city} and wanted to connect. "
            f"At ActTrident, we help engineering teams with {svc_name.lower()} without build friction. Happy to share a brief note."
        )
        body_html = f"<p>{body_text}</p>"
        return subject, body_text, body_html

    subjects, variations = build_email_variations_deterministic(
        company=company,
        contact=contact,
        matched_service_name=svc_name,
        matched_service_code=svc_code,
        tone=tone,
        custom_notes=custom_notes
    )

    v_key = variation_type.lower().strip()
    if "short" in v_key:
        var_data = variations["short"]
    elif "consultative" in v_key or "detailed" in v_key:
        var_data = variations["consultative"]
    else:
        var_data = variations["standard"]

    subject = var_data["subject"]
    body_text = var_data["body_text"]
    body_html = f"<div style=\"font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1e293b; line-height: 1.6; max-width: 600px;\"><p>{body_text.replace(chr(10), '<br/>')}</p></div>"

    return subject, body_text, body_html


def evaluate_email_draft_quality(
    subject: str,
    body_text: str,
    company: Company,
    matched_service_name: Optional[str] = None,
    recipient_name: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """
    Phase 4D AI email quality reviewer.
    Checks company name accuracy, service relevance, unsupported claims, fabricated company facts,
    incorrect personalization, generic introductions, repeated phrases, and subject/body consistency.
    Returns (is_acceptable: bool, issues: List[str]).
    """
    issues: List[str] = []
    subj = (subject or "").strip()
    body = (body_text or "").strip()
    combined = f"{subj}\n{body}"
    combined_low = combined.lower()

    # 1. Unsupported claims & unresolved placeholders
    claims_ok, claim_warnings = validate_message_against_claims(combined)
    if not claims_ok:
        issues.extend([f"unsupported_claim: {w}" for w in claim_warnings])
    placeholders = detect_unresolved_placeholders(combined)
    if placeholders:
        issues.append(f"unresolved_placeholders: {', '.join(placeholders)}")

    # 2. Company name accuracy
    comp_tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9]{3,}", company.name or "") if t.lower() not in ("pvt", "ltd", "private", "limited", "inc", "llp", "the", "and")]
    if comp_tokens and not any(tok in combined_low for tok in comp_tokens[:2]):
        issues.append("company_name_accuracy: target company name missing from subject and body")

    # 3. Fabricated company facts (unverified laptop/headcount numbers)
    if not getattr(company, "has_verified_5_plus_laptops", False) and getattr(company, "laptop_count_verified", None) is None:
        if re.search(r"\b\d{2,4}\s+(?:laptops|workstations|devices|endpoints)\b", combined_low):
            issues.append("fabricated_company_fact: mentions unverified workstation/laptop count")

    # 4. Incorrect personalization
    if recipient_name and "dear sir/madam" in combined_low:
        issues.append("incorrect_personalization: generic 'Dear Sir/Madam' used despite known contact")

    # 5. Generic introductions
    generic_intros = ("i hope this email finds you well", "i hope this finds you well", "my name is", "i am reaching out to introduce")
    for gi in generic_intros:
        if gi in combined_low:
            issues.append(f"generic_introduction: '{gi}'")

    # 6. Repeated phrases (repeated 4-word shingles in body)
    words = re.findall(r"[a-z0-9']+", body.lower())
    if len(words) >= 12:
        shingles = [" ".join(words[i:i + 4]) for i in range(len(words) - 3)]
        seen_shingles = {}
        for sh in shingles:
            seen_shingles[sh] = seen_shingles.get(sh, 0) + 1
        repeated = [sh for sh, cnt in seen_shingles.items() if cnt >= 2 and "unsubscribe" not in sh and "opt out" not in sh]
        if repeated:
            issues.append(f"repeated_phrases: '{repeated[0]}'")

    # 7. Subject/body consistency
    subj_words = {w for w in re.findall(r"[a-z0-9]{4,}", subj.lower()) if w not in ("with", "from", "your", "that", "this", "for", "about")}
    body_words = set(re.findall(r"[a-z0-9]{4,}", body.lower()))
    if subj_words and not (subj_words & body_words):
        issues.append("subject_body_consistency: subject keywords do not appear in body")

    # 8. Service relevance (soft check when service name provided)
    if matched_service_name:
        svc_tokens = {w for w in re.findall(r"[a-z0-9]{4,}", matched_service_name.lower()) if w not in ("service", "services", "solution", "solutions")}
        if svc_tokens and not (svc_tokens & body_words) and "acttrident" not in combined_low:
            issues.append("service_relevance: body lacks connection to matched ActTrident service")

    # Block generation only on severe issues (claims, placeholders, missing company, fabricated facts, repeated phrases)
    severe_prefixes = ("unsupported_claim", "unresolved_placeholders", "company_name_accuracy", "fabricated_company_fact", "repeated_phrases")
    has_severe = any(iss.startswith(severe_prefixes) for iss in issues)
    return (not has_severe), issues


def generate_email_variations(
    db: Session,
    company_id: Optional[int] = None,
    company: Optional[Company] = None,
    contact_id: Optional[int] = None,
    tone: str = "Professional",
    service_id: Optional[int] = None,
    custom_notes: Optional[str] = None
) -> EmailVariationsResponse:
    """
    Generates 3 distinct personalized email variations and 4 subject suggestions for a prospect.
    Strictly forbids generating commercial sales outreach for synthetic test fixtures.
    Grounds all content in verified company evidence, research reports, and approved service catalogue entries.
    """
    if company is None:
        if company_id is None:
            raise ValueError("Either company or company_id must be provided.")
        company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise ValueError(f"Company ID {company_id} not found.")

    # PART 2 & PART 8 MANDATORY GUARD: Never generate real prospect emails for synthetic fixtures
    if _is_synthetic_fixture(company):
        raise ValueError(
            f"Security Policy Block: Company '{company.name}' (ID: {company.id}) is classified as a synthetic "
            f"test fixture or internal demo record ({company.verification_status}). "
            f"Generating commercial sales outreach for synthetic test fixtures is strictly prohibited."
        )

    contact = None
    if contact_id:
        contact = db.query(CompanyContact).filter(CompanyContact.id == contact_id).first()

    recipient_email = (contact.email if contact else None) or company.public_email or company.decision_maker_email
    recipient_name = (contact.name if contact else None) or company.decision_maker_name or "Leadership Team"
    recipient_role = (contact.role if contact else None) or company.decision_maker_role or "Technology Leadership"
    recipient_phone = (contact.phone if contact else None) or company.public_phone or company.public_whatsapp

    # 1. Target Service Resolution
    target_service = None
    if service_id:
        target_service = get_service_by_id(db, service_id)
    elif company.matched_service_id:
        target_service = get_service_by_id(db, company.matched_service_id)

    if not target_service:
        matched = match_service_for_company(company, db=db)
        if matched and matched.service_id:
            target_service = get_service_by_id(db, matched.service_id)
            match_rationale = matched.rationale
            match_confidence = matched.match_confidence
            match_evidence = matched.evidence_supporting_match
            unsupported_assumptions = matched.unsupported_assumptions
        else:
            match_rationale = "No suitable service identified from available commercial evidence."
            match_confidence = 0.0
            match_evidence = "Insufficient technical signals in company profile"
            unsupported_assumptions = ["Requires manual operator review"]
    else:
        match_rationale = f"Matched to {target_service.service_name} based on target profile."
        match_confidence = 0.85
        match_evidence = f"Aligned with {company.industry or 'technology'} sector"
        unsupported_assumptions = []
        if not company.has_verified_5_plus_laptops:
            unsupported_assumptions.append("Laptop fleet size unverified; email avoids device count claims.")

    svc_code = target_service.service_code if target_service else "ACT-WS-01"
    svc_name = target_service.service_name if target_service else "Secure Workspace & Endpoint Isolation"

    # 2. Research Report
    research = db.query(ResearchReport).filter(ResearchReport.company_id == company.id).order_by(ResearchReport.created_at.desc()).first()
    research_summary = research.summary if research else (company.description or f"Commercial enterprise in {company.city}")
    tech_stack = research.likely_tech_requirements if research else "Standard web & software development tools"
    pain_points = research.potential_acttrident_use_cases if research else "Endpoint data leakage prevention & browser posture"

    # 3. Missing Information Audit
    missing_info = []
    if not recipient_email:
        missing_info.append("Public business email address is unverified")
    if not company.decision_maker_name:
        missing_info.append("Direct decision-maker name is unverified (addressing general team leadership)")
    if not company.has_verified_5_plus_laptops:
        missing_info.append("Managed laptop count is unverified (email avoids device count claims)")
    if not company.website:
        missing_info.append("Official company website URL is missing")

    # 4. Source Evidence Compilation
    sources_data = []
    for s in (company.sources or []):
        sources_data.append({
            "field": s.field_name,
            "source_url": s.source_url,
            "source_type": s.source_type,
            "status": s.verification_status
        })
    if not sources_data and company.website:
        sources_data.append({
            "field": "website",
            "source_url": company.website,
            "source_type": "official_website",
            "status": "publicly_listed"
        })

    # 5. Build Content & Variations
    company_context = {
        "company_name": company.name,
        "website": company.website,
        "industry": company.industry,
        "city": company.city,
        "state": company.state,
        "country": company.country,
        "description": company.description,
        "products_and_services": (research.services if research else None) or company.description,
        "recipient_name": recipient_name,
        "recipient_role": recipient_role,
        "recipient_email": recipient_email,
        "recipient_phone": recipient_phone,
        "research_summary": research_summary,
        "tech_stack_observations": tech_stack,
        "it_pain_points": pain_points,
        "missing_information": "; ".join(missing_info) if missing_info else "None",
        "qualification_score": company.qualification_score,
        "qualification_status": company.qualification_status,
        "laptop_count_verified": company.laptop_count_verified,
        "laptop_count_evidence": company.laptop_count_evidence,
        "matched_service_code": svc_code,
        "matched_service_name": svc_name,
        "service_description": target_service.description if target_service else "Workspace isolation and credential shielding",
        "approved_claims": "; ".join(target_service.approved_claims) if target_service else "",
        "disallowed_claims": "; ".join(target_service.disallowed_claims) if target_service else "",
        "service_match_reason": match_rationale,
        "service_match_evidence": match_evidence,
        "unsupported_assumptions": "; ".join(unsupported_assumptions) if unsupported_assumptions else "None",
        "source_evidence": str(sources_data)
    }

    website_verified = _is_website_verified_accessible(company, db)

    # Attempt AI generation via LocalAIGateway (local Ollama) with controlled regeneration on invalid output
    ai_success = False
    ai_result = None
    for attempt in range(2):
        try:
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                import concurrent.futures
                ai_timeout = float(getattr(settings, "OLLAMA_TIMEOUT_SECONDS", 60))
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    ai_result = pool.submit(
                        asyncio.run,
                        local_ai_gateway.generate_phase3_email_variations(company_context, tone=tone)
                    ).result(timeout=ai_timeout)
            else:
                ai_result = loop.run_until_complete(
                    local_ai_gateway.generate_phase3_email_variations(company_context, tone=tone)
                )

            if ai_result and isinstance(ai_result, dict) and "variation_a_short" in ai_result:
                var_keys = ["variation_a_short", "variation_b_standard", "variation_c_detailed"]
                all_valid = True
                for vk in var_keys:
                    v_obj = ai_result.get(vk, {})
                    v_subj = (v_obj.get("subject") or "").strip()
                    v_body = (v_obj.get("body_text") or "").strip()
                    if not v_subj or not v_body:
                        all_valid = False
                        break
                    claims_ok, claim_errs = validate_message_against_claims(f"{v_subj}\n{v_body}")
                    placeholders = detect_unresolved_placeholders(f"{v_subj}\n{v_body}")
                    quality_ok, quality_issues = evaluate_email_draft_quality(
                        subject=v_subj,
                        body_text=v_body,
                        company=company,
                        matched_service_name=svc_name,
                        recipient_name=recipient_name,
                    )
                    if not claims_ok or placeholders or not quality_ok:
                        logger.warning(
                            f"AI output attempt {attempt + 1} failed validation for {company.name}: "
                            f"claims_ok={claims_ok}, placeholders={placeholders}, quality_issues={quality_issues}"
                        )
                        all_valid = False
                        break
                if all_valid:
                    # Also ensure no placeholders in subject_suggestions
                    suggs = ai_result.get("subject_suggestions", [])
                    if any(detect_unresolved_placeholders(s) for s in suggs):
                        all_valid = False
                if all_valid:
                    ai_success = True
                    break
        except Exception as exc:
            logger.info(f"Ollama AI generation attempt {attempt + 1} failed ({exc}); {'retrying' if attempt == 0 else 'using deterministic copywriter'}.")

    if not ai_success or not ai_result:
        # Deterministic generation conforming strictly to all ActTrident rules
        det_subjects, det_variations = build_email_variations_deterministic(
            company=company,
            contact=contact,
            matched_service_name=svc_name,
            matched_service_code=svc_code,
            tone=tone,
            custom_notes=custom_notes,
            research_summary=research_summary,
            website_verified=website_verified,
        )
        subject_suggestions = det_subjects
        var_items = [
            EmailVariationItem(
                variation_type="short",
                label="Short Professional Introduction",
                subject=det_variations["short"]["subject"],
                body_text=det_variations["short"]["body_text"],
                body_html=f"<p>{det_variations['short']['body_text'].replace(chr(10), '<br/>')}</p>",
                tone=tone,
                description=det_variations["short"]["description"]
            ),
            EmailVariationItem(
                variation_type="standard",
                label="Standard Personalized Business Email",
                subject=det_variations["standard"]["subject"],
                body_text=det_variations["standard"]["body_text"],
                body_html=f"<p>{det_variations['standard']['body_text'].replace(chr(10), '<br/>')}</p>",
                tone=tone,
                description=det_variations["standard"]["description"]
            ),
            EmailVariationItem(
                variation_type="consultative",
                label="Detailed Consultative Email",
                subject=det_variations["consultative"]["subject"],
                body_text=det_variations["consultative"]["body_text"],
                body_html=f"<p>{det_variations['consultative']['body_text'].replace(chr(10), '<br/>')}</p>",
                tone=tone,
                description=det_variations["consultative"]["description"]
            )
        ]
        model_used = "deterministic-copywriter-v3"
    else:
        subject_suggestions = ai_result.get("subject_suggestions", [
            f"{svc_name} for {company.name}",
            f"Workspace protection overview for {company.name}"
        ])
        var_a = ai_result.get("variation_a_short", {})
        var_b = ai_result.get("variation_b_standard", {})
        var_c = ai_result.get("variation_c_detailed", {})

        body_a = ensure_opt_out_sentence(var_a.get("body_text", ""))
        body_b = ensure_opt_out_sentence(var_b.get("body_text", ""))
        body_c = ensure_opt_out_sentence(var_c.get("body_text", ""))

        var_items = [
            EmailVariationItem(
                variation_type="short",
                label="Short Professional Introduction",
                subject=var_a.get("subject", subject_suggestions[0]),
                body_text=body_a,
                body_html=f"<p>{body_a.replace(chr(10), '<br/>')}</p>",
                tone=tone,
                description="Short Professional Introduction (3 concise paragraphs)"
            ),
            EmailVariationItem(
                variation_type="standard",
                label="Standard Personalized Business Email",
                subject=var_b.get("subject", subject_suggestions[1] if len(subject_suggestions) > 1 else subject_suggestions[0]),
                body_text=body_b,
                body_html=f"<p>{body_b.replace(chr(10), '<br/>')}</p>",
                tone=tone,
                description="Standard Personalized Business Email (comprehensive company context & solution fit)"
            ),
            EmailVariationItem(
                variation_type="consultative",
                label="Detailed Consultative Email",
                subject=var_c.get("subject", subject_suggestions[2] if len(subject_suggestions) > 2 else subject_suggestions[0]),
                body_text=body_c,
                body_html=f"<p>{body_c.replace(chr(10), '<br/>')}</p>",
                tone=tone,
                description="Detailed Consultative Email (approved capabilities & operational fit)"
            )
        ]
        model_used = "llama3.2:latest"

    return EmailVariationsResponse(
        company_id=company.id,
        company_name=company.name,
        website=company.website,
        city=company.city,
        industry=company.industry,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        recipient_role=recipient_role,
        recipient_phone=recipient_phone,
        matched_service_code=svc_code,
        matched_service_name=svc_name,
        service_match_reason=match_rationale,
        service_match_evidence=match_evidence,
        service_match_confidence=match_confidence,
        unsupported_assumptions=unsupported_assumptions,
        missing_information=missing_info,
        source_evidence=sources_data,
        subject_suggestions=subject_suggestions,
        variations=var_items,
        generation_model=model_used,
        is_synthetic=False
    )


def generate_email_draft(
    db: Session,
    company: Company,
    contact_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    tone: str = "Professional",
    draft_type: str = "initial_email",
    variation_type: str = "standard",
    service_id: Optional[int] = None,
    custom_notes: Optional[str] = None
) -> EmailDraft:
    """
    Creates a new AI-generated personalized outreach draft in 'draft' status awaiting mandatory human approval.
    Strictly forbids generating commercial sales outreach for synthetic test fixtures.
    Binds service code, generation model, variation type, and source evidence into the draft record.
    """
    # PART 2 & PART 8 MANDATORY GUARD
    if _is_synthetic_fixture(company):
        raise ValueError(
            f"Security Policy Block: Company '{company.name}' (ID: {company.id}) is a synthetic test fixture "
            f"({company.verification_status}). Generating commercial sales outreach for synthetic fixtures is strictly prohibited."
        )

    contact = None
    if contact_id:
        contact = db.query(CompanyContact).filter(CompanyContact.id == contact_id).first()

    recipient_email = (contact.email if contact else None) or company.public_email or company.decision_maker_email
    recipient_name = (contact.name if contact else None) or company.decision_maker_name or "Leadership Team"

    # PART 2 MANDATORY VALIDATION: Validate recipient email syntax before generating commercial email draft
    if draft_type not in ("whatsapp_draft", "linkedin_message"):
        recipient_email = validate_recipient_email_syntax(recipient_email)

    # 1. Target Service Resolution
    target_service = None
    if service_id:
        target_service = get_service_by_id(db, service_id)
    elif company.matched_service_id:
        target_service = get_service_by_id(db, company.matched_service_id)

    if not target_service:
        matched = match_service_for_company(company, db=db)
        if matched and matched.service_id:
            target_service = get_service_by_id(db, matched.service_id)

    target_service_name = target_service.service_name if target_service else "Secure Workspace & Endpoint Isolation"
    target_service_code = target_service.service_code if target_service else "ACT-WS-01"
    service_desc = target_service.description if target_service else None

    # 2. Build Content
    subject, body_text, body_html = build_email_content(
        company=company,
        contact=contact,
        tone=tone,
        draft_type=draft_type,
        variation_type=variation_type,
        target_service_name=target_service_name,
        service_description=service_desc,
        custom_notes=custom_notes
    )

    # 3. Suppression Registry Check
    clean_rec = (recipient_email or "").strip().lower()
    suppressed = None
    if clean_rec:
        suppressed = db.query(SuppressionList).filter(SuppressionList.identifier == clean_rec).first()
    if not suppressed and company.website:
        host = (urlparse(company.website).hostname or "").replace("www.", "").lower()
        if host:
            suppressed = db.query(SuppressionList).filter(SuppressionList.identifier == host).first()

    # 4. Strict Claims, Placeholder & Policy Validation
    unresolved_ph = detect_unresolved_placeholders(f"{subject}\n{body_text}")
    if unresolved_ph:
        raise ValueError(f"Generated email contains unresolved template placeholders: {unresolved_ph}")

    valid_claims, claim_warnings = validate_message_against_claims(f"{subject}\n{body_text}")
    policy_violation = None
    try:
        CompliancePolicyEngine.validate_outreach_text(subject, body_text)
    except PolicyViolationError as pve:
        policy_violation = str(pve)

    if suppressed:
        approval_status = "rejected"
        rejection_reason = f"Recipient or domain is registered on suppression list ({suppressed.reason})"
    elif not valid_claims:
        logger.warning(f"Claims validation rejected draft for {company.name}: {claim_warnings}")
        approval_status = "rejected"
        rejection_reason = f"Unsupported product claims detected: {'; '.join(claim_warnings)}"
    elif policy_violation:
        approval_status = "rejected"
        rejection_reason = policy_violation
    else:
        approval_status = "draft"
        rejection_reason = None

    # Compile subjects suggestions
    det_subjects, _ = build_email_variations_deterministic(
        company=company,
        contact=contact,
        matched_service_name=target_service_name,
        matched_service_code=target_service_code,
        tone=tone,
        custom_notes=custom_notes,
        website_verified=_is_website_verified_accessible(company, db),
    )

    # Compile missing info
    missing_items = []
    if not recipient_email:
        missing_items.append("Recipient email address unverified")
    if not company.decision_maker_name:
        missing_items.append("Decision maker unverified (addressing general leadership)")
    if not company.has_verified_5_plus_laptops:
        missing_items.append("Managed laptop fleet unverified")

    # Compile source evidence
    sources_summary = [s.source_url for s in (company.sources or []) if s.source_url]
    if not sources_summary and company.website:
        sources_summary.append(company.website)

    draft = EmailDraft(
        campaign_id=campaign_id,
        company_id=company.id,
        contact_id=contact_id,
        recipient_email=recipient_email or "",
        recipient_name=recipient_name,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        tone=tone,
        approval_status=approval_status,
        rejection_reason=rejection_reason,
        provider="smtp",
        generation_model="deterministic-copywriter-v3",
        matched_service_code=target_service_code,
        matched_service_name=target_service_name,
        variation_type=variation_type,
        subject_suggestions=json.dumps(det_subjects),
        source_evidence=json.dumps(sources_summary),
        missing_information=json.dumps(missing_items)
    )
    db.add(draft)

    # Update CRM lead status to 'draft_ready' if currently 'new' or 'qualified' and email is available
    if company.lead and company.lead.pipeline_status in ["new", "researching", "qualified"]:
        company.lead.pipeline_status = "draft_ready" if recipient_email else "needs_contact_info"

    db.commit()
    db.refresh(draft)
    return draft
