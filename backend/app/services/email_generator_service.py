from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyContact
from app.models.campaign import Campaign
from app.models.email import EmailDraft
from app.schemas.email import EmailGenerateRequest


def build_email_content(
    company: Company,
    contact: Optional[CompanyContact],
    tone: str,
    custom_notes: Optional[str] = None
) -> tuple[str, str, str]:
    """Builds an 8-part personalized email adhering strictly to ActTrident messaging rules."""
    
    recipient_name = (contact.name if contact else None) or company.decision_maker_name or "Team"
    city = company.city
    industry = company.industry or "technology"
    has_laptops = company.has_verified_5_plus_laptops
    laptop_count = company.laptop_count_verified or "5+"

    # 1. Subject Line (Non-deceptive, clear value proposition)
    if tone == "Technical":
        subject = f"ActTrident Endpoint Security & Browser Isolation for {company.name}"
    elif tone == "Formal":
        subject = f"Proposed 90-Day Enterprise Evaluation: ActTrident Workspace Protection for {company.name}"
    elif tone == "Short introductory":
        subject = f"ActTrident Workspace Protection for {company.name} in {city}"
    elif tone == "Follow-up":
        subject = f"Follow-up: 90-Day Free Evaluation of ActTrident for {company.name}"
    else:  # Friendly professional
        subject = f"ActTrident 90-day Evaluation Program for {company.name} ({city})"

    # 2. Greeting
    if tone == "Formal":
        greeting = f"Dear {recipient_name},"
    else:
        greeting = f"Hello {recipient_name},"

    # 3. Short introduction to ActTrident
    intro = (
        "I am reaching out from ActTrident (https://acttrident.ai/). "
        "We specialize in enterprise endpoint protection and browser workspace security designed specifically "
        "to safeguard distributed workstations and modern cloud workflows."
    )

    # 4. Relevant reason for approaching that company
    if has_laptops:
        approach_reason = (
            f"We noticed {company.name}'s growing technical operations in {city} and your team's deployment of "
            f"managed laptops. Companies in the {industry} sector often require rigorous security controls "
            "around client deliverables and web-based development environments."
        )
    else:
        approach_reason = (
            f"We are actively collaborating with forward-thinking {industry} organizations in {city}. "
            "As engineering teams increasingly manage proprietary source code and client data through web tools, "
            "endpoint posture and browser security become pivotal."
        )

    # 5. Accurate description of product capabilities
    if tone == "Technical":
        capabilities = (
            "ActTrident provides non-intrusive runtime workspace protection, zero-trust browser credential isolation, "
            "and centralized device posture verification. It prevents unauthorized data exfiltration without impairing "
            "developer productivity or software build performance."
        )
    else:
        capabilities = (
            "ActTrident provides lightweight, non-intrusive protection for company laptops. "
            "It isolates sensitive browser sessions, safeguards corporate accounts, and ensures devices accessing "
            "your business services maintain verified security compliance."
        )

    # 6. Invitation to demonstration
    demo_invitation = "We would welcome the opportunity to share a concise 15-minute product overview tailored to your environment."

    # 7. Proposed 90-day evaluation programme
    eval_proposal = (
        f"For eligible companies managing at least five company laptops, we are currently offering a "
        f"proposed 90-day free product evaluation. This allows your team to experience ActTrident's capabilities "
        "in your actual environment with full technical support and zero obligation."
    )

    # 8. Simple meeting request
    meeting_request = (
        "Would you be open to a brief 15-minute introductory call next Tuesday or Wednesday to discuss whether "
        "this evaluation program is a fit for your team?"
    )

    # 9. Professional signature
    signature_text = (
        "Best regards,\n"
        "Business Development Team | ActTrident\n"
        "https://acttrident.ai/ | outreach@acttrident.ai"
    )

    # Assemble Plain Text Body
    body_text = f"""{greeting}

{intro}

{approach_reason}

{capabilities}

{demo_invitation}

{eval_proposal}

{meeting_request}

{signature_text}"""

    # Assemble HTML Body
    body_html = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6; max-width: 600px;">
  <p>{greeting}</p>
  <p>{intro}</p>
  <p>{approach_reason}</p>
  <p>{capabilities}</p>
  <p>{demo_invitation}</p>
  <div style="background-color: #f1f5f9; border-left: 4px solid #2563eb; padding: 12px 16px; margin: 16px 0; border-radius: 2px;">
    <strong>Proposed Evaluation:</strong> {eval_proposal}
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
    custom_notes: Optional[str] = None
) -> EmailDraft:
    """Creates a new AI-generated personalized email in 'draft' status awaiting human approval."""
    
    contact = None
    if contact_id:
        from app.models.company import CompanyContact
        contact = db.query(CompanyContact).filter(CompanyContact.id == contact_id).first()

    recipient_email = (contact.email if contact else None) or company.public_email or company.decision_maker_email
    if not recipient_email:
        recipient_email = f"contact@{company.name.lower().replace(' ', '')}.example.com"

    recipient_name = (contact.name if contact else None) or company.decision_maker_name

    subject, body_text, body_html = build_email_content(
        company=company,
        contact=contact,
        tone=tone,
        custom_notes=custom_notes
    )

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
        approval_status="draft",  # ALWAYS draft initially (Mandatory Human Approval)
        provider="smtp"
    )
    db.add(draft)

    # Update CRM lead status to 'draft_ready' if currently 'new' or 'qualified'
    if company.lead and company.lead.pipeline_status in ["new", "researching", "qualified"]:
        company.lead.pipeline_status = "draft_ready"

    db.commit()
    db.refresh(draft)
    return draft
