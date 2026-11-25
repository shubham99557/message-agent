from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.core.crypto import encrypt_secret, mask_secret
from app.core.audit import record_audit_log
from app.models.user import User
from app.models.activity import AuditLog, IntegrationCredential, SuppressionList
from app.schemas.settings import IntegrationConfigUpdate, IntegrationConfigResponse, AuditLogResponse
from app.services.orchestration_service import get_kill_switch_status, set_kill_switch

router = APIRouter()


class KillSwitchToggleRequest(BaseModel):
    active: bool
    reason: Optional[str] = None


def _serialize_integration(cred: IntegrationCredential) -> IntegrationConfigResponse:
    return IntegrationConfigResponse(
        id=cred.id,
        provider=cred.provider,
        key_identifier=cred.key_identifier,
        has_secret=bool(cred.encrypted_value),
        masked_value=mask_secret(cred.encrypted_value) if cred.encrypted_value else None,
        is_active=cred.is_active,
        updated_at=cred.updated_at
    )


@router.get("/integrations", response_model=List[IntegrationConfigResponse])
def get_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    creds = db.query(IntegrationCredential).all()
    return [_serialize_integration(c) for c in creds]


@router.post("/integrations", response_model=IntegrationConfigResponse)
def save_integration(
    config_in: IntegrationConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    encrypted = encrypt_secret(config_in.encrypted_value) if config_in.encrypted_value else None
    cred = db.query(IntegrationCredential).filter(IntegrationCredential.provider == config_in.provider).first()
    if not cred:
        cred = IntegrationCredential(
            provider=config_in.provider,
            key_identifier=config_in.key_identifier,
            encrypted_value=encrypted,
            is_active=config_in.is_active
        )
        db.add(cred)
    else:
        cred.key_identifier = config_in.key_identifier
        if encrypted:
            cred.encrypted_value = encrypted
        cred.is_active = config_in.is_active

    db.commit()
    db.refresh(cred)

    # Apply immediately to runtime settings (decrypted strictly in memory)
    from app.main import apply_saved_integrations
    apply_saved_integrations(db)
    record_audit_log(
        db=db,
        action="save_integration",
        entity_type="integration",
        entity_id=str(cred.id),
        user_id=current_user.id,
        details={"provider": cred.provider, "is_active": cred.is_active}
    )
    return _serialize_integration(cred)


@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()


class SuppressionCreate(BaseModel):
    identifier: str
    channel: str = "all"
    reason: str = "manual_suppression"


@router.get("/suppression-list", response_model=List[dict])
def get_suppression_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    items = db.query(SuppressionList).order_by(SuppressionList.created_at.desc()).all()
    return [
        {
            "id": i.id,
            "identifier": i.identifier,
            "channel": i.channel,
            "reason": i.reason,
            "created_at": i.created_at
        } for i in items
    ]


@router.post("/suppression-list", status_code=status.HTTP_201_CREATED)
def add_to_suppression_list(
    payload: SuppressionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    clean_id = payload.identifier.strip().lower()
    existing = db.query(SuppressionList).filter(SuppressionList.identifier == clean_id).first()
    if existing:
        return {"id": existing.id, "identifier": existing.identifier, "status": "already_present"}
    item = SuppressionList(
        identifier=clean_id,
        channel=payload.channel,
        reason=payload.reason,
        source=f"operator:{current_user.email}"
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    record_audit_log(
        db=db,
        action="add_suppression",
        entity_type="suppression",
        entity_id=str(item.id),
        user_id=current_user.id,
        details={"identifier": clean_id, "reason": payload.reason}
    )
    return {"id": item.id, "identifier": item.identifier, "status": "added"}


@router.delete("/suppression-list/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_suppression_list(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    item = db.query(SuppressionList).filter(SuppressionList.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Suppression entry not found")
    record_audit_log(
        db=db,
        action="remove_suppression",
        entity_type="suppression",
        entity_id=str(item.id),
        user_id=current_user.id,
        details={"identifier": item.identifier}
    )
    db.delete(item)
    db.commit()
    return None


@router.get("/kill-switch")
def read_kill_switch(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns live status of the Global Emergency Outbound Kill Switch."""
    return get_kill_switch_status(db)


@router.post("/kill-switch")
def toggle_kill_switch(
    req: KillSwitchToggleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Activates or deactivates the Global Emergency Outbound Kill Switch immediately (Admin/Manager only)."""
    return set_kill_switch(db=db, active=req.active, user_id=current_user.id, reason=req.reason)
