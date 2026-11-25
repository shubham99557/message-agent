from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


CHANNEL_CONNECTION_STATUSES = [
    "connected",
    "disconnected",
    "reauth_required",
    "error",
    "sandbox"
]


class ChannelConnection(Base):
    """
    Stores encrypted OAuth / API credentials and live connection status for external communication
    channels (Gmail API, SMTP, Meta WhatsApp Cloud API, Authorized LinkedIn).
    Credentials are strictly Fernet-encrypted at rest and separated from business prospect tables.
    """
    __tablename__ = "channel_connections"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String(50), nullable=False, index=True)  # gmail, smtp, whatsapp, linkedin
    account_identifier = Column(String(255), nullable=True, index=True)  # Gmail email, WA phone_number_id, etc.
    display_name = Column(String(255), nullable=True)

    status = Column(String(50), default="disconnected", nullable=False, index=True)
    is_sandbox = Column(Boolean, default=False, nullable=False)

    # Fernet-encrypted secret tokens (NEVER returned in API responses)
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    scopes = Column(Text, nullable=True)  # Space-separated granted scopes

    # Operational sync state
    last_synced_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    connected_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    connected_by = relationship("User")
