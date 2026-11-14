from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json
from sqlalchemy.orm import Session


def record_audit_log(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
):
    """Safely records an immutable audit log entry."""
    from app.models.activity import AuditLog

    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        ip_address=ip_address,
        details=json.dumps(details) if details else None,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(log_entry)
    try:
        db.commit()
    except Exception:
        db.rollback()
