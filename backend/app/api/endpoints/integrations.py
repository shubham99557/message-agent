from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.core.audit import record_audit_log
from app.models.user import User
from app.integrations.gmail_adapter import (
    build_gmail_authorization_url,
    verify_oauth_state,
    exchange_code_for_tokens,
    get_active_gmail_connection,
    sync_gmail_replies,
    disconnect_gmail_connection,
    get_email_channel_status,
    GmailIntegrationError,
    GMAIL_OAUTH_SCOPES,
)

router = APIRouter()


@router.get("/gmail/status")
def gmail_connection_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns honest email channel status (Gmail OAuth 2.0, SMTP fallback, or Mock Simulation)."""
    return get_email_channel_status(db)


@router.get("/gmail/oauth/start")
def start_gmail_oauth(
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Generates a CSRF-protected Google OAuth 2.0 consent URL with least-privilege Gmail scopes."""
    try:
        auth_url, state = build_gmail_authorization_url(current_user.id)
        return {
            "authorization_url": auth_url,
            "state": state,
            "scopes": GMAIL_OAUTH_SCOPES,
        }
    except GmailIntegrationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/gmail/oauth/callback")
def gmail_oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Handles Google OAuth 2.0 callback, validates CSRF state, and persists encrypted tokens."""
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth authorization denied: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth 'code' or 'state' parameter.")

    user_id = verify_oauth_state(state)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth CSRF state parameter.")

    try:
        conn = exchange_code_for_tokens(db=db, code=code, user_id=user_id)
    except GmailIntegrationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    record_audit_log(
        db=db,
        action="gmail_oauth_connected",
        entity_type="channel_connection",
        entity_id=str(conn.id),
        user_id=user_id,
        details={"account_email": conn.account_identifier, "status": conn.status}
    )
    return {
        "status": "connected",
        "channel": "gmail",
        "account_email": conn.account_identifier,
        "display_name": conn.display_name,
        "scopes": conn.scopes,
        "token_expires_at": conn.token_expires_at.isoformat() if conn.token_expires_at else None,
    }


@router.post("/gmail/sync-replies")
def trigger_gmail_reply_sync(
    max_results: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Synchronizes incoming Gmail replies and provider bounce notifications."""
    conn = get_active_gmail_connection(db)
    if not conn or conn.status != "connected":
        raise HTTPException(
            status_code=400,
            detail="Gmail OAuth is not connected. Connect a Gmail account before syncing replies."
        )
    try:
        result = sync_gmail_replies(db=db, connection=conn, max_results=max_results)
    except GmailIntegrationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    record_audit_log(
        db=db,
        action="gmail_sync_replies",
        entity_type="channel_connection",
        entity_id=str(conn.id),
        user_id=current_user.id,
        details={"synced_replies": result["synced_replies"], "bounces_recorded": result["bounces_recorded"]}
    )
    return result


@router.post("/gmail/disconnect")
def disconnect_gmail(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Revokes Gmail OAuth credentials and disconnects the mailbox."""
    conn = get_active_gmail_connection(db)
    if not conn:
        raise HTTPException(status_code=404, detail="No Gmail connection exists.")

    disconnect_gmail_connection(db=db, connection=conn)
    record_audit_log(
        db=db,
        action="gmail_oauth_disconnected",
        entity_type="channel_connection",
        entity_id=str(conn.id),
        user_id=current_user.id,
        details={"account_email": conn.account_identifier}
    )
    return {"status": "disconnected", "channel": "gmail"}
