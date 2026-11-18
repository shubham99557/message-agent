from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User
from app.models.activity import AuditLog, IntegrationCredential, SuppressionList
from app.schemas.settings import IntegrationConfigUpdate, IntegrationConfigResponse, AuditLogResponse

router = APIRouter()


@router.get("/integrations", response_model=List[IntegrationConfigResponse])
def get_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    creds = db.query(IntegrationCredential).all()
    return creds


@router.post("/integrations", response_model=IntegrationConfigResponse)
def save_integration(
    config_in: IntegrationConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    cred = db.query(IntegrationCredential).filter(IntegrationCredential.provider == config_in.provider).first()
    if not cred:
        cred = IntegrationCredential(
            provider=config_in.provider,
            key_identifier=config_in.key_identifier,
            encrypted_value=config_in.encrypted_value,
            is_active=config_in.is_active
        )
        db.add(cred)
    else:
        cred.key_identifier = config_in.key_identifier
        if config_in.encrypted_value:
            cred.encrypted_value = config_in.encrypted_value
        cred.is_active = config_in.is_active

    db.commit()
    db.refresh(cred)

    # Apply immediately to runtime settings so no restart is required
    from app.main import apply_saved_integrations
    from app.core.audit import record_audit_log
    apply_saved_integrations(db)
    record_audit_log(
        db=db,
        action="save_integration",
        entity_type="integration",
        entity_id=str(cred.id),
        user_id=current_user.id,
        details={"provider": cred.provider, "is_active": cred.is_active}
    )
    return cred


@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()


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
