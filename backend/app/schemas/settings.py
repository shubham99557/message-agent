from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict


class IntegrationConfigUpdate(BaseModel):
    provider: str  # gemini, openai, smtp, gmail, whatsapp_meta
    key_identifier: Optional[str] = None
    encrypted_value: Optional[str] = None
    is_active: bool = True


class IntegrationConfigResponse(BaseModel):
    id: int
    provider: str
    key_identifier: Optional[str] = None
    is_active: bool
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: Optional[str] = None
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)
