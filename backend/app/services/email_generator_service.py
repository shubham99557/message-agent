from datetime import datetime, timezone
from typing import Optional, Tuple
from urllib.parse import urlparse
import logging
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyContact
from app.models.campaign import Campaign
from app.models.email import EmailDraft
from app.models.activity import SuppressionList
from app.schemas.email import EmailGenerateRequest
from app.core.config import settings
from app.core.product_claims import validate_message_against_claims
from app.services.service_catalogue_service import get_service_by_id, match_service_for_company

logger = logging.getLogger("acttrident.email_generator")


def build_email_content(
    company: Company,
    contact: Optional[CompanyContact],
    tone: str = "Professional",
    draft_type: str = "initial_email",
    target_service_name: Optional[str] = None,
    service_description: Optional[str] = None,
    custom_notes: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Builds structured, personalized outreach content strictly adhering to ActTrident messaging rules.
    Supports draft types: initial_email, followup_email, short_intro, whatsapp_draft, linkedin_message.
    Supports styles: Professional, Concise, Consultative, Technical.
    """
    recipient_name = (contact.name if contact else None) or company.decision_maker_name or "Team"
    city = company.city or "India"
    industry = company.industry or "technology"
    has_laptops = company.has_verified_5_plus_laptops
    laptop_count = company.laptop_count_verified or "5+"
    svc_name = target_service_name or company.matched_service_name or "Secure Workspace & Endpoint Isolation"

    # Tone normalization
    clean_tone = tone.strip().lower()
    clean_type = draft_type.strip().lower()

    # 1. Subject Line
    if clean_type == "whatsapp_draft":
        subject = f"ActTrident inquiry regarding {company.name}"
    elif clean_type == "linkedin_message":
        subject = f"Connecting re: {svc_name} at {company.name}"
    elif clean_type == "short_intro":
        subject = f"{svc_name} for {company.name}"
    elif clean_type == "followup_email":
        subject = f"Following up: {svc_name} for {company.name}"
    elif "technical" in clean_tone:
        subject = f"ActTrident: {svc_name} architecture overview for {company.name}"
    elif "concise" in clean_tone:
        subject = f"Quick note: {svc_name} for {company.name}"
    elif "consultative" in clean_tone:
        subject = f"Addressing {industry} endpoint & security challenges at {company.name}"
    else:  # Professional
        subject = f"{svc_name} for {company.name} ({city})"

    # 2. Greeting
    if "concise" in clean_tone or clean_type in ("whatsapp_draft", "linkedin_message"):
        greeting = f"Hi {recipient_name},"
    elif "formal" in clean_tone:
        greeting = f"Dear {recipient_name},"
    else:
        greeting = f"Hello {recipient_name},"

    # 3. Channel-Specific Layouts
    if clean_type == "whatsapp_draft":
        # Compliant conversational WhatsApp draft
        body_text = (
            f"{greeting}\n\n"
            f"Reaching out from ActTrident regarding {company.name}'s technology operations in {city}.\n"
            f"We provide {svc_name.lower()} to help engineering teams safeguard source code and cloud credentials.\n\n"
            f"Would you be open to a 5-minute chat or receiving a short technical overview?\n\n"
            f"— ActTrident Team (https://acttrident.ai/)"
        )
        body_html = f"<p>{body_text.replace(chr(10), '<br/>')}</p>"
        return subject, body_text, body_html

    if clean_type == "linkedin_message":
        # Concise LinkedIn connection note / message
        body_text = (
            f"{greeting}\n\n"
            f"I came across {company.name}'s impressive work in {industry}. "
            f"At ActTrident, we help technology leaders implement {svc_name.lower()} without slowing down developer velocity.\n\n"
            f"Would love to connect and share a brief look at how other teams in {city} approach this.\n\n"
            f"Best regards,\nActTrident Team"
        )
        body_html = f"<p>{body_text.replace(chr(10), '<br/>')}</p>"
        return subject, body_text, body_html

    if clean_type == "short_intro" or "concise" in clean_tone:
        # Concise direct intro
        body_text = (
            f"{greeting}\n\n"
            f"I'm reaching out from ActTrident. We noticed {company.name}'s technical presence in {city}.\n\n"
            f"We specialize in {svc_name}: protecting code repositories, browser sessions, and cloud credentials from unauthorized data leakage.\n\n"
            f"Are you open to a brief 10-minute technical exchange next week?\n\n"
            f"Best regards,\n"
            f"ActTrident Team\nhttps://acttrident.ai/"
        )
        body_html = f"""<div style="font-family: sans-serif; line-height: 1.5; color: #1e293b;">
  <p>{greeting}</p>
  <p>I'm reaching out from ActTrident. We noticed {company.name}'s technical presence in {city}.</p>
  <p>We specialize in <strong>{svc_name}</strong>: protecting code repositories, browser sessions, and cloud credentials from unauthorized data leakage.</p>
  <p>Are you open to a brief 10-minute technical exchange next week?</p>
  <p>Best regards,<br/><strong>ActTrident Team</strong><br/><a href="https://acttrident.ai/">https://acttrident.ai/</a></p>
</div>"""
        return subject, body_text, body_html

    # Standard Multi-Part Outreach (Professional, Consultative, Technical, Follow-up)
    intro = (
        "I am reaching out from ActTrident (https://acttrident.ai/). "
        f"We specialize in {svc_name.lower()} designed specifically "
        "to safeguard distributed workstations and modern cloud workflows."
    )

    if has_laptops:
        approach_reason = (
            f"We noticed {company.name}'s technical operations in {city} and your team's deployment of "
            f"managed laptops. Companies in the {industry} sector often require rigorous security controls "
            "around client deliverables and web-based development environments."
        )
    else:
        approach_reason = (
            f"We are actively collaborating with forward-thinking {industry} organizations in {city}. "
            "As engineering teams increasingly manage proprietary source code and client data through web tools, "
            "endpoint posture and browser security become pivotal."
        )

    if "technical" in clean_tone:
        capabilities = (
            f"ActTrident provides non-intrusive runtime workspace protection, zero-trust browser credential isolation, "
            f"and centralized device posture verification. It prevents unauthorized data exfiltration without impairing "
            f"developer productivity or software build performance."
        )
    elif "consultative" in clean_tone:
        capabilities = (
            f"For high-growth {industry} firms, balancing developer flexibility with client confidentiality is critical. "
            f"ActTrident's {svc_name.lower()} delivers granular clipboard protection, isolated cloud access, and zero data leakage "
            f"without requiring heavy, intrusive device surveillance."
        )
    else:
        capabilities = (
            f"ActTrident delivers lightweight, non-intrusive workspace protection. "
            f"It isolates sensitive browser sessions, safeguards corporate accounts, and ensures devices accessing "
            f"your business services maintain verified security compliance."
        )

    demo_invitation = "We would welcome the opportunity to share a concise 15-minute product overview tailored to your environment."

    allow_eval_offer = getattr(settings, "ALLOW_90_DAY_EVALUATION_OFFER", False)
    if allow_eval_offer and has_laptops:
        eval_proposal = (
            f"For eligible companies managing at least five company laptops, we are currently offering a "
            f"proposed 90-day free product evaluation. This allows your team to experience ActTrident's capabilities "
            f"in your actual environment with full technical support and zero obligation."
        )
    else:
        eval_proposal = (
            "We offer a streamlined technical assessment and live demonstration tailored to your workflow, "
            "allowing your team to evaluate ActTrident's browser workspace protection with zero disruption to active development."
        )

    meeting_request = (
        "Would you be open to a brief 15-minute introductory call next Tuesday or Wednesday to discuss whether "
        "this is a fit for your team?"
    )

    signature_text = (
        "Best regards,\n"
        "Business Development Team | ActTrident\n"
        "https://acttrident.ai/ | outreach@acttrident.ai"
    )

    body_text = f"""{greeting}

{intro}

{approach_reason}

{capabilities}

{demo_invitation}

{eval_proposal}

{meeting_request}

{signature_text}"""

    body_html = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6; max-width: 600px;">
  <p>{greeting}</p>
  <p>{intro}</p>
  <p>{approach_reason}</p>
  <p>{capabilities}</p>
  <p>{demo_invitation}</p>
  <div style="background-color: #f1f5f9; border-left: 4px solid #2563eb; padding: 12px 16px; margin: 16px 0; border-radius: 2px;">
    <strong>Proposed Solution:</strong> {eval_proposal}
  </div>
  <p>{meeting_request}</p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
  <p style="color: #64748b; font-size: 13px;">
    <strong>ActTrident Business Development</strong><br/>
    Website: <a href="https://acttrident.ai/" style="color: #2563eb; text-decoration: none;">https://acttrident.ai/</a><br/>
    Contact: <a href="mailto:outreach@acttrident.ai" style="color: #2563eb; text-decoration: none;">outreach@acttrident.ai</a>
  </p>
</div>"""

    return subject, body_text, body_html


def generate_email_draft(
    db: Session,
    company: Company,
    contact_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    tone: str = "Friendly professional",
    draft_type: str = "initial_email",
    service_id: Optional[int] = None,
    custom_notes: Optional[str] = None
) -> EmailDraft:
    """Creates a new AI-generated personalized outreach draft in 'draft' status awaiting human approval."""
    contact = None
    if contact_id:
        contact = db.query(CompanyContact).filter(CompanyContact.id == contact_id).first()

    recipient_email = (contact.email if contact else None) or company.public_email or company.decision_maker_email
    recipient_name = (contact.name if contact else None) or company.decision_maker_name

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
    service_desc = target_service.description if target_service else None

    # 2. Build Content
    subject, body_text, body_html = build_email_content(
        company=company,
        contact=contact,
        tone=tone,
        draft_type=draft_type,
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

    # 4. Strict Claims Validation
    valid_claims, claim_warnings = validate_message_against_claims(f"{subject}\n{body_text}")

    if suppressed:
        approval_status = "rejected"
        rejection_reason = f"Recipient or domain is registered on suppression list ({suppressed.reason})"
    elif not valid_claims:
        logger.warning(f"Claims validation rejected draft for {company.name}: {claim_warnings}")
        approval_status = "rejected"
        rejection_reason = f"Unsupported product claims detected: {'; '.join(claim_warnings)}"
    elif not recipient_email and draft_type not in ("whatsapp_draft", "linkedin_message"):
        approval_status = "missing_recipient"
        rejection_reason = "Missing recipient email address."
    else:
        approval_status = "draft"
        rejection_reason = None

    draft = EmailDraft(
        campaign_id=campaign_id,
        company_id=company.id,
        contact_id=contact_id,
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        tone=tone,
        approval_status=approval_status,
        rejection_reason=rejection_reason,
        provider="smtp"
    )
    db.add(draft)

    # Update CRM lead status to 'draft_ready' if currently 'new' or 'qualified' and email is available
    if company.lead and company.lead.pipeline_status in ["new", "researching", "qualified"]:
        company.lead.pipeline_status = "draft_ready" if recipient_email else "needs_contact_info"

    db.commit()
    db.refresh(draft)
    return draft
