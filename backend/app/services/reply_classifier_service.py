import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.reply import Conversation, Reply, REPLY_CATEGORIES
from app.models.company import Company
from app.models.lead import Lead
from app.services.crm_service import handle_opt_out


def classify_reply_text(message_text: str) -> tuple[str, float, str, str, bool]:
    """Classifies inbound response into 10 categories, generates suggested reply and checks negotiation."""
    text_lower = message_text.lower().strip()

    # 1. Unsubscribe / Opt-out
    if any(k in text_lower for k in ["unsubscribe", "stop", "remove me", "don't email", "do not contact", "opt out"]):
        classification = "unsubscribe"
        confidence = 0.99
        reason = "Explicit request to unsubscribe or stop communication."
        suggested = "You have been removed from our contact list. We apologize for any inconvenience."
        is_negotiation = False

    # 2. Not interested
    elif any(k in text_lower for k in ["not interested", "no thanks", "no need", "we already have", "pass on this"]):
        classification = "not_interested"
        confidence = 0.95
        reason = "Prospect expressed lack of current interest or existing vendor relationship."
        suggested = "Thank you for letting us know. Should your team require workspace protection in the future, we would be glad to reconnect."
        is_negotiation = False

    # 3. Demonstration request
    elif any(k in text_lower for k in ["demo", "demonstration", "show me", "walk through", "presentation"]):
        classification = "requests_demonstration"
        confidence = 0.96
        reason = "Prospect requested a product demonstration."
        suggested = "Thank you for your interest! We would be delighted to schedule a 15-minute walkthrough. Here is a scheduling link or let us know if next Wednesday at 3 PM IST works for you."
        is_negotiation = True

    # 4. Pricing request
    elif any(k in text_lower for k in ["price", "pricing", "cost", "quote", "commercials", "how much"]):
        classification = "requests_pricing"
        confidence = 0.95
        reason = "Prospect enquired about pricing or commercials."
        suggested = "During the initial phase, eligible teams with 5+ managed laptops receive the proposed 90-day evaluation at zero cost. After the evaluation, pricing is tailored to fleet size. Let us arrange a brief call to understand your setup."
        is_negotiation = True

    # 5. Wants a callback
    elif any(k in text_lower for k in ["call me", "call back", "phone number", "speak on phone", "give me a ring"]):
        classification = "wants_a_callback"
        confidence = 0.94
        reason = "Prospect requested a telephone callback."
        suggested = "We will be pleased to call you. What is the best number and preferred time to reach you?"
        is_negotiation = False

    # 6. Out of office
    elif any(k in text_lower for k in ["out of office", "on leave", "automatic reply", "away from my desk", "vacation"]):
        classification = "out_of_office"
        confidence = 0.98
        reason = "Automated out-of-office autoreply."
        suggested = ""
        is_negotiation = False

    # 7. Wrong contact
    elif any(k in text_lower for k in ["wrong person", "not in charge", "no longer with", "forwarded to", "contact our"]):
        classification = "wrong_contact"
        confidence = 0.92
        reason = "Recipient indicates they are not the appropriate contact or refers to a colleague."
        suggested = "Thank you for letting us know. Could you kindly share the name or email of the team member responsible for laptop and workspace security?"
        is_negotiation = False

    # 8. Partnership
    elif any(k in text_lower for k in ["partner", "partnership", "reseller", "collaborate", "distributor"]):
        classification = "potential_partnership"
        confidence = 0.90
        reason = "Inquiry regarding channel partnership or reseller collaboration."
        suggested = "Thank you for reaching out regarding partnership opportunities with ActTrident. Our strategic alliance team would be glad to discuss synergy."
        is_negotiation = True

    # 9. Interested
    elif any(k in text_lower for k in ["interested", "sounds good", "let's connect", "share more", "tell me more", "details"]):
        classification = "interested"
        confidence = 0.93
        reason = "Prospect displayed explicit interest in ActTrident or the 90-day evaluation."
        suggested = "We are thrilled to connect! We would love to share how ActTrident protects developer workstations. Would a 15-minute call on Thursday morning suit your calendar?"
        is_negotiation = True

    # 10. Wants more information (Default)
    else:
        classification = "wants_more_information"
        confidence = 0.85
        reason = "Prospect asked for clarification or general details."
        suggested = "Thank you for your message. ActTrident provides non-intrusive workspace and browser protection for teams managing 5+ laptops. Would you prefer a brief technical brief or an interactive demo?"
        is_negotiation = False

    return classification, confidence, reason, suggested, is_negotiation


def ingest_inbound_reply(
    db: Session,
    channel: str,
    sender_identifier: str,
    recipient_identifier: str,
    subject: Optional[str],
    message_body: str
) -> Reply:
    """Ingests incoming reply, classifies into 10 categories, creates suggested response and updates CRM."""
    
    # 1. Match company by sender email or phone
    clean_sender = sender_identifier.strip().lower()
    company = db.query(Company).filter(
        or_(
            Company.public_email.ilike(clean_sender),
            Company.public_phone.ilike(f"%{clean_sender}%"),
            Company.public_whatsapp.ilike(f"%{clean_sender}%")
        )
    ).first()

    if not company:
        # Create unassociated placeholder company if new prospect reached out
        company = Company(
            name=f"Inbound Lead ({clean_sender})",
            city="Siliguri",
            public_email=clean_sender if "@" in clean_sender else None,
            public_phone=clean_sender if "@" not in clean_sender else None,
            qualification_status="Needs manual verification"
        )
        db.add(company)
        db.flush()

    # 2. Find or create Conversation thread
    conv = db.query(Conversation).filter(
        Conversation.company_id == company.id,
        Conversation.channel == channel
    ).first()
    if not conv:
        conv = Conversation(
            company_id=company.id,
            channel=channel,
            subject=subject or "Inbound Discussion",
            last_message_at=datetime.now(timezone.utc)
        )
        db.add(conv)
        db.flush()
    else:
        conv.last_message_at = datetime.now(timezone.utc)

    # 3. Classify reply
    classification, confidence, reason, suggested, is_negotiation = classify_reply_text(message_body)

    reply = Reply(
        conversation_id=conv.id,
        company_id=company.id,
        channel=channel,
        sender_identifier=sender_identifier,
        recipient_identifier=recipient_identifier,
        subject=subject,
        message_body=message_body,
        classification=classification,
        classification_confidence=confidence,
        classification_reason=reason,
        suggested_response=suggested,
        is_negotiation=is_negotiation,
        human_approved=False,  # Negotiated replies require human signoff!
        is_handled=False,
        received_at=datetime.now(timezone.utc)
    )
    db.add(reply)

    # 4. Update CRM Pipeline based on reply
    if company.lead:
        company.lead.last_contact_date = datetime.now(timezone.utc)
        if classification in ["unsubscribe", "not_interested"]:
            # Opt-out immediately halts promotional follow-ups!
            handle_opt_out(db, identifier=sender_identifier, channel=channel, reason=classification)
        elif classification in ["interested", "requests_demonstration", "requests_pricing"]:
            company.lead.pipeline_status = "interested"
        elif classification == "out_of_office":
            pass  # Keep current status
        else:
            company.lead.pipeline_status = "replied"

    db.commit()
    db.refresh(reply)
    return reply
