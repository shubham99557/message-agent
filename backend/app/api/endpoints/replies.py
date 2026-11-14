from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.reply import Reply, Conversation, REPLY_CATEGORIES
from app.schemas.reply import InboundReplyCreate, ReplyResponse, SuggestedResponseApproval
from app.services.reply_classifier_service import ingest_inbound_reply
from app.core.audit import record_audit_log

router = APIRouter()


@router.post("/inbound", response_model=ReplyResponse, status_code=status.HTTP_201_CREATED)
def receive_inbound_reply(
    payload: InboundReplyCreate,
    db: Session = Depends(get_db)
):
    reply = ingest_inbound_reply(
        db=db,
        channel=payload.channel,
        sender_identifier=payload.sender_identifier,
        recipient_identifier=payload.recipient_identifier,
        subject=payload.subject,
        message_body=payload.message_body
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
    replies = query.order_by(Reply.received_at.desc()).offset(skip).limit(limit).all()

    items = [
        ReplyResponse(
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
        ) for r in replies
    ]

    return {
        "items": items,
        "total": total,
        "available_categories": REPLY_CATEGORIES
    }


@router.post("/{reply_id}/approve-response", response_model=ReplyResponse)
def approve_reply_response(
    reply_id: int,
    payload: SuggestedResponseApproval,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    reply = db.query(Reply).filter(Reply.id == reply_id).first()
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")

    if payload.approved_text:
        reply.suggested_response = payload.approved_text

    reply.human_approved = True
    reply.is_handled = True
    db.commit()

    record_audit_log(
        db=db,
        action="approve_negotiated_reply",
        entity_type="reply",
        entity_id=str(reply.id),
        user_id=current_user.id,
        details={"sender": reply.sender_identifier}
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
