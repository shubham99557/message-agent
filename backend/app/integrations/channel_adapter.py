"""
Unified Multi-Channel Integration Adapter Architecture.

Defines a single common `ChannelAdapter` interface implemented cleanly across:
1. EmailChannelAdapter (Gmail OAuth 2.0 + SMTP + honest simulation mode)
2. WhatsAppChannelAdapter (Official Meta WhatsApp Cloud API + strict live consent)
3. LinkedInChannelAdapter (Official LinkedIn OAuth 2.0 / Partner API + compliant manual handoff)
"""
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.integrations.gmail_adapter import (
    build_gmail_authorization_url,
    disconnect_gmail_connection,
    get_active_gmail_connection,
    get_email_channel_status,
    sync_gmail_replies,
)
from app.integrations.whatsapp_adapter import (
    check_meta_connection_health,
    get_whatsapp_connection_status,
)
from app.integrations.linkedin_adapter import (
    build_linkedin_authorization_url,
    disconnect_linkedin_connection,
    get_active_linkedin_connection,
    get_linkedin_connection_status,
    validate_linkedin_profile_url,
)
from app.models.activity import SuppressionList


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,10}$")
E164_RE = re.compile(r"^\+?[1-9]\d{7,14}$")


class ChannelAdapter(ABC):
    """Common contract for every ActTrident outreach communication channel."""

    channel_name: str

    @abstractmethod
    def connect(self, db: Session, user_id: int, **kwargs: Any) -> Dict[str, Any]:
        """Initiates connection / OAuth authorization or verifies provider credentials."""

    @abstractmethod
    def connection_status(self, db: Session) -> Dict[str, Any]:
        """Returns honest live connection, mode, and configuration status."""

    @abstractmethod
    def validate_recipient(self, db: Session, recipient_identifier: str, **kwargs: Any) -> Tuple[bool, str]:
        """Validates recipient format, consent/policy requirements, and suppression status."""

    @abstractmethod
    def prepare_message(self, db: Session, company_id: int, payload: Dict[str, Any], user_id: int) -> Any:
        """Creates a draft message requiring human approval."""

    @abstractmethod
    def send_approved_message(self, db: Session, message_id: int, user_id: int, **kwargs: Any) -> Dict[str, Any]:
        """Dispatches an explicitly approved message via the channel's compliant transport."""

    @abstractmethod
    def receive_event(self, db: Session, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Records a provider delivery/bounce/read event."""

    @abstractmethod
    def process_webhook(self, db: Session, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        """Processes an inbound provider webhook payload."""

    @abstractmethod
    def sync_conversation(self, db: Session, **kwargs: Any) -> Dict[str, Any]:
        """Synchronizes inbound replies / conversations from the external provider."""

    @abstractmethod
    def disconnect(self, db: Session, user_id: int) -> Dict[str, Any]:
        """Revokes tokens / disconnects the external channel safely."""


class EmailChannelAdapter(ChannelAdapter):
    channel_name = "email"

    def connect(self, db: Session, user_id: int, **kwargs: Any) -> Dict[str, Any]:
        auth_url, state = build_gmail_authorization_url(user_id)
        return {"channel": "email", "authorization_url": auth_url, "state": state}

    def connection_status(self, db: Session) -> Dict[str, Any]:
        status = get_email_channel_status(db)
        return {"channel": "email", **status}

    def validate_recipient(self, db: Session, recipient_identifier: str, **kwargs: Any) -> Tuple[bool, str]:
        email = (recipient_identifier or "").strip().lower()
        if not EMAIL_RE.match(email):
            return False, "Invalid email address format."
        suppressed = (
            db.query(SuppressionList)
            .filter(SuppressionList.identifier == email, SuppressionList.channel.in_(["all", "email"]))
            .first()
        )
        if suppressed:
            return False, f"Recipient '{email}' is on the suppression list ({suppressed.reason})."
        return True, "valid"

    def prepare_message(self, db: Session, company_id: int, payload: Dict[str, Any], user_id: int) -> Any:
        from app.models.company import Company
        from app.services.email_generator_service import generate_email_draft

        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise ValueError("Company not found.")
        return generate_email_draft(
            db=db,
            company=company,
            campaign_id=payload.get("campaign_id"),
            tone=payload.get("tone", "Friendly professional"),
            custom_notes=payload.get("custom_notes"),
        )

    def send_approved_message(self, db: Session, message_id: int, user_id: int, **kwargs: Any) -> Dict[str, Any]:
        from app.services.email_sender_service import send_approved_email

        return send_approved_email(db=db, draft_id=message_id, user_id=user_id)

    def receive_event(self, db: Session, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        from app.models.email import EmailEvent

        ev = EmailEvent(
            draft_id=event_payload["draft_id"],
            event_type=event_payload["event_type"],
            details=event_payload.get("details"),
        )
        db.add(ev)
        db.commit()
        return {"status": "recorded", "event_id": ev.id}

    def process_webhook(self, db: Session, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        return self.receive_event(db, payload)

    def sync_conversation(self, db: Session, **kwargs: Any) -> Dict[str, Any]:
        conn = get_active_gmail_connection(db)
        if not conn or conn.status != "connected":
            return {"status": "disconnected", "synced_replies": 0, "bounces_recorded": 0}
        return sync_gmail_replies(db=db, connection=conn, max_results=int(kwargs.get("max_results", 20)))

    def disconnect(self, db: Session, user_id: int) -> Dict[str, Any]:
        conn = get_active_gmail_connection(db)
        if not conn:
            return {"channel": "email", "status": "already_disconnected"}
        disconnect_gmail_connection(db=db, connection=conn)
        return {"channel": "email", "status": "disconnected"}


class WhatsAppChannelAdapter(ChannelAdapter):
    channel_name = "whatsapp"

    def connect(self, db: Session, user_id: int, **kwargs: Any) -> Dict[str, Any]:
        return check_meta_connection_health()

    def connection_status(self, db: Session) -> Dict[str, Any]:
        status = get_whatsapp_connection_status(db)
        return {"channel": "whatsapp", **status}

    def validate_recipient(self, db: Session, recipient_identifier: str, **kwargs: Any) -> Tuple[bool, str]:
        from app.services.whatsapp_service import verify_active_whatsapp_consent

        phone = re.sub(r"[\s\-\(\)]", "", (recipient_identifier or "").strip())
        if not E164_RE.match(phone):
            return False, "Invalid WhatsApp phone number (expected E.164 format)."
        suppressed = (
            db.query(SuppressionList)
            .filter(SuppressionList.identifier == phone, SuppressionList.channel.in_(["all", "whatsapp"]))
            .first()
        )
        if suppressed:
            return False, f"Recipient '{phone}' is on the suppression list."
        company_id = kwargs.get("company_id")
        if company_id is not None:
            has_consent, reason = verify_active_whatsapp_consent(db, int(company_id), phone)
            if not has_consent:
                return False, reason
        return True, "valid"

    def prepare_message(self, db: Session, company_id: int, payload: Dict[str, Any], user_id: int) -> Any:
        from app.schemas.whatsapp import WhatsAppMessageCreate
        from app.services.whatsapp_service import create_whatsapp_message

        req = WhatsAppMessageCreate(
            company_id=company_id,
            recipient_phone=payload["recipient_phone"],
            template_name=payload["template_name"],
            template_variables=payload.get("template_variables", {}),
        )
        return create_whatsapp_message(db=db, msg_in=req, user_id=user_id)

    def send_approved_message(self, db: Session, message_id: int, user_id: int, **kwargs: Any) -> Dict[str, Any]:
        from app.services.whatsapp_service import send_approved_whatsapp_message

        return send_approved_whatsapp_message(db=db, message_id=message_id, user_id=user_id)

    def receive_event(self, db: Session, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        from app.services.whatsapp_service import process_meta_webhook_payload

        return process_meta_webhook_payload(db=db, payload=event_payload)

    def process_webhook(self, db: Session, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        from app.services.whatsapp_service import process_meta_webhook_payload

        return process_meta_webhook_payload(db=db, payload=payload)

    def sync_conversation(self, db: Session, **kwargs: Any) -> Dict[str, Any]:
        return {"channel": "whatsapp", "mode": "webhook_driven", "note": "WhatsApp inbound messages arrive via signed Meta Cloud API webhooks."}

    def disconnect(self, db: Session, user_id: int) -> Dict[str, Any]:
        return {"channel": "whatsapp", "status": "managed_via_environment_or_integration_credentials"}


class LinkedInChannelAdapter(ChannelAdapter):
    channel_name = "linkedin"

    def connect(self, db: Session, user_id: int, **kwargs: Any) -> Dict[str, Any]:
        auth_url, state = build_linkedin_authorization_url(user_id)
        return {"channel": "linkedin", "authorization_url": auth_url, "state": state}

    def connection_status(self, db: Session) -> Dict[str, Any]:
        return get_linkedin_connection_status(db)

    def validate_recipient(self, db: Session, recipient_identifier: str, **kwargs: Any) -> Tuple[bool, str]:
        ok, reason = validate_linkedin_profile_url(recipient_identifier)
        if not ok:
            return False, reason
        suppressed = (
            db.query(SuppressionList)
            .filter(
                SuppressionList.identifier == recipient_identifier.strip().lower(),
                SuppressionList.channel.in_(["all", "linkedin"]),
            )
            .first()
        )
        if suppressed:
            return False, "LinkedIn profile is on the global suppression list."
        return True, "valid"

    def prepare_message(self, db: Session, company_id: int, payload: Dict[str, Any], user_id: int) -> Any:
        from app.schemas.linkedin import LinkedInDraftCreate
        from app.services.linkedin_service import create_linkedin_draft

        draft_in = LinkedInDraftCreate(
            company_id=company_id,
            campaign_id=payload.get("campaign_id"),
            recipient_name=payload.get("recipient_name"),
            recipient_profile_url=payload.get("recipient_profile_url"),
            message_type=payload.get("message_type", "connection_note"),
            tone=payload.get("tone", "Consultative"),
            custom_message=payload.get("custom_message"),
            custom_notes=payload.get("custom_notes"),
        )
        return create_linkedin_draft(db=db, draft_in=draft_in, user_id=user_id)

    def send_approved_message(self, db: Session, message_id: int, user_id: int, **kwargs: Any) -> Dict[str, Any]:
        from app.services.linkedin_service import dispatch_approved_linkedin_message

        return dispatch_approved_linkedin_message(
            db=db,
            message_id=message_id,
            user_id=user_id,
            http_client=kwargs.get("http_client"),
        )

    def receive_event(self, db: Session, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"channel": "linkedin", "status": "unsupported_without_partner_webhook"}

    def process_webhook(self, db: Session, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        return {"channel": "linkedin", "status": "unsupported_without_partner_webhook"}

    def sync_conversation(self, db: Session, **kwargs: Any) -> Dict[str, Any]:
        return {
            "channel": "linkedin",
            "status": "manual_or_partner_only",
            "note": "LinkedIn standard OAuth apps do not expose inbox message sync; log replies via Inbox or approved Partner API.",
        }

    def disconnect(self, db: Session, user_id: int) -> Dict[str, Any]:
        conn = get_active_linkedin_connection(db)
        if not conn:
            return {"channel": "linkedin", "status": "already_disconnected"}
        disconnect_linkedin_connection(db=db, connection=conn)
        return {"channel": "linkedin", "status": "disconnected"}


_ADAPTER_REGISTRY: Dict[str, ChannelAdapter] = {
    "email": EmailChannelAdapter(),
    "whatsapp": WhatsAppChannelAdapter(),
    "linkedin": LinkedInChannelAdapter(),
}


def get_channel_adapter(channel: str) -> ChannelAdapter:
    key = (channel or "").strip().lower()
    if key == "gmail":
        key = "email"
    adapter = _ADAPTER_REGISTRY.get(key)
    if not adapter:
        raise ValueError(f"Unknown channel adapter '{channel}'. Supported: {list(_ADAPTER_REGISTRY.keys())}")
    return adapter


def list_all_channel_statuses(db: Session) -> Dict[str, Any]:
    """Returns unified honest status across Email, WhatsApp, and LinkedIn."""
    return {
        "channels": {
            name: adapter.connection_status(db)
            for name, adapter in _ADAPTER_REGISTRY.items()
        }
    }
