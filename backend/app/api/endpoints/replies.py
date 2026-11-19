from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User
from app.models.reply import Reply, Conversation, REPLY_CATEGORIES
from app.schemas.reply import InboundReplyCreate, ReplyResponse, SuggestedResponseApproval
from app.services.reply_classifier_service import ingest_inbound_reply
from app.core.audit import record_audit_log

router = APIRouter()


@router.post("/inbound", response_model=ReplyResponse, status_code=status.HTTP_201_CREATED)
def receive_inbound_reply(
    payload: InboundReplyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Authenticated endpoint for ingesting verified incoming customer communications."""
    reply = ingest_inbound_reply(
        db=db,
        channel=payload.channel,
        sender_identifier=payload.sender_identifier,
        recipient_identifier=payload.recipient_identifier,
        subject=payload.subject,
        message_body=payload.message_body
    )
    record_audit_log(
        db=db,
        action="ingest_inbound_reply",
        entity_type="reply",
        entity_id=str(reply.id),
        user_id=current_user.id,
        details={"sender": reply.sender_identifier, "channel": reply.channel}
    )
    return ReplyResponse(
        id=reply.id,
        conversation_id=reply.conversation_id,
        company_id=reply.company_id,
        channel=reply.channel,
        sender_identifier=reply.sender_identifier,
        recipient_identifier=reply.recipient_identifier,
        subject=reply.subject,
        message_body=reply.message_body,
        classification=reply.classification,
        classification_confidence=reply.classification_confidence,
        classification_reason=reply.classification_reason,
        suggested_response=reply.suggested_response,
        is_negotiation=reply.is_negotiation,
        human_approved=reply.human_approved,
        is_handled=reply.is_handled,
        received_at=reply.received_at,
        company_name=reply.company.name if reply.company else None
    )


@router.get("/inbox", response_model=dict)
def get_inbox_messages(
    classification: Optional[str] = None,
    channel: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Reply)
    if classification and classification.lower() != "all":
        query = query.filter(Reply.classification == classification)
    if channel and channel.lower() != "all":
        query = query.filter(Reply.channel == channel)

    total = query.count()
    items = query.order_by(Reply.received_at.desc()).offset(skip).limit(limit).all()

    enriched_items = []
    for r in items:
        enriched_items.append(ReplyResponse(
            id=r.id,
            conversation_id=r.conversation_id,
            company_id=r.company_id,
            channel=r.channel,
            sender_identifier=r.sender_identifier,
            recipient_identifier=r.recipient_identifier,
            subject=r.subject,
            message_body=r.message_body,
            classification=r.classification,
            classification_confidence=r.classification_confidence,
            classification_reason=r.classification_reason,
            suggested_response=r.suggested_response,
            is_negotiation=r.is_negotiation,
            human_approved=r.human_approved,
            is_handled=r.is_handled,
            received_at=r.received_at,
            company_name=r.company.name if r.company else None
        ))

    return {
        "items": enriched_items,
        "total": total,
        "categories": REPLY_CATEGORIES
    }


@router.post("/approve-response", response_model=dict)
@router.post("/{reply_id}/approve-response", response_model=dict)
def approve_suggested_response(
    approval: SuggestedResponseApproval,
    reply_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Requires manager or admin sign-off before sending suggested responses to business negotiations."""
    target_id = reply_id or approval.reply_id
    reply = db.query(Reply).filter(Reply.id == target_id).first()
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")

    reply.human_approved = approval.approved
    reply.is_handled = True
    if approval.edited_response:
        reply.suggested_response = approval.edited_response
    db.commit()

    record_audit_log(
        db=db,
        action="approve_negotiation_reply" if reply.is_negotiation else "approve_reply_response",
        entity_type="reply",
        entity_id=str(reply.id),
        user_id=current_user.id,
        details={"approved": approval.approved}
    )

    return {
        "status": "success",
        "reply_id": reply.id,
        "is_negotiation": reply.is_negotiation,
        "approved": approval.approved,
        "human_approved": reply.human_approved
    }
