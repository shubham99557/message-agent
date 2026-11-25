"""
Autonomous Sales Orchestration & Safety Controls Service.

Provides:
1. Global Emergency Outbound Kill Switch ("Stop All Outbound Sending") persisted in `system_settings`.
2. Campaign lifecycle controls (`pause`, `resume`, `stop`) enforced at dispatch time.
3. Asia/Kolkata (IST) business-hours guard for automated follow-up scheduling.
4. Transactional `OutboundDispatchOutbox` for crash-safe, idempotent multi-channel dispatch.
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.audit import record_audit_log
from app.models.campaign import Campaign
from app.models.orchestration import SystemSetting, OutboundDispatchOutbox

logger = logging.getLogger("acttrident.orchestration")

KILL_SWITCH_KEY = "global_outbound_kill_switch"
KILL_SWITCH_REASON_KEY = "global_outbound_kill_switch_reason"
IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


def _get_setting(db: Session, key: str) -> Optional[SystemSetting]:
    return db.query(SystemSetting).filter(SystemSetting.key == key).first()


def _upsert_setting(db: Session, key: str, value: str, user_id: Optional[int], description: Optional[str] = None) -> SystemSetting:
    row = _get_setting(db, key)
    now = datetime.now(timezone.utc)
    if not row:
        row = SystemSetting(
            key=key,
            value=value,
            description=description,
            updated_by_user_id=user_id,
            updated_at=now,
        )
        db.add(row)
    else:
        row.value = value
        if description is not None:
            row.description = description
        row.updated_by_user_id = user_id
        row.updated_at = now
    return row


def is_kill_switch_active(db: Session) -> Tuple[bool, Optional[str]]:
    """Checks whether the Global Emergency Outbound Kill Switch is active."""
    flag = _get_setting(db, KILL_SWITCH_KEY)
    if flag and flag.value.strip().lower() in ("true", "1", "yes", "active"):
        reason_row = _get_setting(db, KILL_SWITCH_REASON_KEY)
        reason = reason_row.value if reason_row and reason_row.value else "Emergency outbound halt activated by operator."
        return True, reason
    return False, None


def get_kill_switch_status(db: Session) -> Dict[str, Any]:
    active, reason = is_kill_switch_active(db)
    flag = _get_setting(db, KILL_SWITCH_KEY)
    return {
        "active": active,
        "reason": reason,
        "updated_at": flag.updated_at.isoformat() if flag and flag.updated_at else None,
        "updated_by_user_id": flag.updated_by_user_id if flag else None,
    }


def set_kill_switch(db: Session, active: bool, user_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
    """Activates or deactivates the Global Emergency Outbound Kill Switch with full audit logging."""
    clean_reason = (reason or ("Emergency stop activated" if active else "Resumed normal outbound operations")).strip()
    _upsert_setting(
        db=db,
        key=KILL_SWITCH_KEY,
        value="true" if active else "false",
        user_id=user_id,
        description="Emergency kill switch that immediately blocks all outbound sending across Email, WhatsApp, and LinkedIn.",
    )
    _upsert_setting(
        db=db,
        key=KILL_SWITCH_REASON_KEY,
        value=clean_reason,
        user_id=user_id,
        description="Operator reason for current kill switch state.",
    )
    db.commit()

    record_audit_log(
        db=db,
        action="kill_switch_activated" if active else "kill_switch_deactivated",
        entity_type="system_setting",
        entity_id=KILL_SWITCH_KEY,
        user_id=user_id,
        details={"active": active, "reason": clean_reason},
    )
    return get_kill_switch_status(db)


def is_within_ist_business_hours(
    now_utc: Optional[datetime] = None,
    start_hour: int = 9,
    end_hour: int = 18,
    allow_saturday: bool = False,
) -> Tuple[bool, str]:
    """
    Checks whether the given timestamp falls within Asia/Kolkata (IST, UTC+05:30)
    business hours (default: Mon-Fri 09:00-18:00 IST).
    """
    ref = now_utc or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    ist_dt = ref.astimezone(IST_OFFSET)
    weekday = ist_dt.weekday()  # 0=Mon .. 5=Sat, 6=Sun
    max_weekday = 5 if allow_saturday else 4
    if weekday > max_weekday:
        return False, f"Outside IST business days ({ist_dt.strftime('%A %H:%M IST')})"
    if not (start_hour <= ist_dt.hour < end_hour):
        return False, f"Outside IST business hours {start_hour:02d}:00-{end_hour:02d}:00 ({ist_dt.strftime('%H:%M IST')})"
    return True, f"Within IST business hours ({ist_dt.strftime('%A %H:%M IST')})"


def check_campaign_allows_dispatch(db: Session, campaign_id: Optional[int]) -> Tuple[bool, Optional[str]]:
    """Verifies that a campaign is neither paused nor stopped before allowing outbound dispatch."""
    if not campaign_id:
        return True, None
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        return True, None
    if camp.status in ("paused", "stopped"):
        return False, f"Campaign '{camp.name}' is currently '{camp.status}'; outbound dispatch is blocked."
    return True, None


def cancel_campaign_outbox(db: Session, campaign_id: int, reason: str) -> int:
    """Cancels any pending outbox items for a paused or stopped campaign."""
    now = datetime.now(timezone.utc)
    count = (
        db.query(OutboundDispatchOutbox)
        .filter(
            OutboundDispatchOutbox.campaign_id == campaign_id,
            OutboundDispatchOutbox.status == "pending",
        )
        .update(
            {
                "status": "cancelled",
                "last_error": reason,
                "processed_at": now,
            },
            synchronize_session=False,
        )
    )
    return count


def pause_campaign(db: Session, campaign_id: int, user_id: int) -> Tuple[Campaign, int]:
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        raise ValueError("Campaign not found.")
    if camp.status == "stopped":
        raise ValueError("Campaign is permanently stopped and cannot be paused.")
    camp.status = "paused"
    cancelled = cancel_campaign_outbox(db, campaign_id, "Campaign paused by operator")
    db.commit()
    db.refresh(camp)
    record_audit_log(
        db=db,
        action="campaign_paused",
        entity_type="campaign",
        entity_id=str(camp.id),
        user_id=user_id,
        details={"cancelled_outbox_items": cancelled},
    )
    return camp, cancelled


def resume_campaign(db: Session, campaign_id: int, user_id: int) -> Campaign:
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        raise ValueError("Campaign not found.")
    if camp.status == "stopped":
        raise ValueError("Campaign was permanently stopped and cannot be resumed. Create a new campaign instead.")
    camp.status = "active"
    db.commit()
    db.refresh(camp)
    record_audit_log(
        db=db,
        action="campaign_resumed",
        entity_type="campaign",
        entity_id=str(camp.id),
        user_id=user_id,
        details={"status": camp.status},
    )
    return camp


def stop_campaign(db: Session, campaign_id: int, user_id: int) -> Tuple[Campaign, int]:
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not camp:
        raise ValueError("Campaign not found.")
    camp.status = "stopped"
    cancelled = cancel_campaign_outbox(db, campaign_id, "Campaign permanently stopped by operator")
    db.commit()
    db.refresh(camp)
    record_audit_log(
        db=db,
        action="campaign_stopped",
        entity_type="campaign",
        entity_id=str(camp.id),
        user_id=user_id,
        details={"cancelled_outbox_items": cancelled},
    )
    return camp, cancelled


def enqueue_outbox_dispatch(
    db: Session,
    channel: str,
    entity_id: int,
    user_id: int,
    campaign_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
) -> OutboundDispatchOutbox:
    """
    Idempotently writes an approved message into the durable transactional outbox.
    Blocks enqueuing if the Global Kill Switch is active or campaign is paused/stopped.
    """
    ks_active, ks_reason = is_kill_switch_active(db)
    if ks_active:
        raise ValueError(f"Blocked: Global Outbound Kill Switch is ACTIVE ({ks_reason}).")

    camp_ok, camp_err = check_campaign_allows_dispatch(db, campaign_id)
    if not camp_ok:
        raise ValueError(camp_err)

    key = idempotency_key or f"outbox:{channel}:{entity_id}"
    existing = db.query(OutboundDispatchOutbox).filter(OutboundDispatchOutbox.idempotency_key == key).first()
    if existing:
        return existing

    row = OutboundDispatchOutbox(
        channel=channel.strip().lower(),
        entity_id=entity_id,
        campaign_id=campaign_id,
        idempotency_key=key,
        status="pending",
        attempts=0,
        max_attempts=3,
        created_by_user_id=user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def process_outbox_batch(db: Session, user_id: int, limit: int = 20) -> Dict[str, Any]:
    """
    Processes pending/retryable transactional outbox items safely:
    - Immediately halts if Global Kill Switch is active.
    - Cancels items belonging to paused/stopped campaigns.
    - Claims each item atomically (`pending` -> `processing`) to prevent duplicate dispatch.
    - Retries transient failures with exponential backoff until `max_attempts` is exhausted.
    """
    ks_active, ks_reason = is_kill_switch_active(db)
    if ks_active:
        return {
            "processed": 0,
            "dispatched": 0,
            "failed": 0,
            "cancelled": 0,
            "halted_by_kill_switch": True,
            "reason": ks_reason,
        }

    from app.services.email_sender_service import send_approved_email
    from app.services.whatsapp_service import send_approved_whatsapp_message
    from app.services.linkedin_service import dispatch_approved_linkedin_message

    now = datetime.now(timezone.utc)
    candidates = (
        db.query(OutboundDispatchOutbox)
        .filter(
            OutboundDispatchOutbox.status == "pending",
            (OutboundDispatchOutbox.next_retry_at == None) | (OutboundDispatchOutbox.next_retry_at <= now),
        )
        .order_by(OutboundDispatchOutbox.created_at.asc())
        .limit(limit)
        .all()
    )

    dispatched = 0
    failed = 0
    cancelled = 0

    for item in candidates:
        # Re-check kill switch before every single item
        ks_now, _ = is_kill_switch_active(db)
        if ks_now:
            break

        # Check campaign pause/stop
        camp_ok, camp_err = check_campaign_allows_dispatch(db, item.campaign_id)
        if not camp_ok:
            item.status = "cancelled"
            item.last_error = camp_err
            item.processed_at = datetime.now(timezone.utc)
            db.commit()
            cancelled += 1
            continue

        # Atomic conditional claim (pending -> processing)
        claimed = (
            db.query(OutboundDispatchOutbox)
            .filter(OutboundDispatchOutbox.id == item.id, OutboundDispatchOutbox.status == "pending")
            .update({"status": "processing", "attempts": item.attempts + 1}, synchronize_session=False)
        )
        db.commit()
        if claimed == 0:
            continue
        db.refresh(item)

        try:
            if item.channel == "email":
                res = send_approved_email(db=db, draft_id=item.entity_id, user_id=user_id)
                if res.status in ("sent", "simulated", "smtp_accepted"):
                    item.status = "dispatched"
                    item.result_summary = json.dumps({"status": res.status, "provider": res.provider})
                    item.processed_at = datetime.now(timezone.utc)
                    dispatched += 1
                elif res.status in ("blocked_recent_contact", "blocked_suppression"):
                    # Terminal policy blocks: the draft was rejected, retrying cannot succeed.
                    item.status = "cancelled"
                    item.last_error = (res.message or res.status)[:500]
                    item.processed_at = datetime.now(timezone.utc)
                    cancelled += 1
                else:
                    raise RuntimeError(res.message or f"Email send returned status '{res.status}'")
            elif item.channel == "whatsapp":
                ok, msg = send_approved_whatsapp_message(db=db, message_id=item.entity_id, user_id=user_id)
                if ok:
                    item.status = "dispatched"
                    item.result_summary = json.dumps({"status": "dispatched", "message": msg})
                    item.processed_at = datetime.now(timezone.utc)
                    dispatched += 1
                else:
                    raise RuntimeError(msg)
            elif item.channel == "linkedin":
                res = dispatch_approved_linkedin_message(db=db, message_id=item.entity_id, user_id=user_id)
                item.status = "dispatched"
                item.result_summary = json.dumps({"status": res.get("status"), "delivery_mode": res.get("delivery_mode")})
                item.processed_at = datetime.now(timezone.utc)
                dispatched += 1
            else:
                raise ValueError(f"Unsupported outbox channel '{item.channel}'")
            db.commit()
        except Exception as exc:
            item.last_error = str(exc)[:500]
            if item.attempts >= item.max_attempts:
                item.status = "failed"
                item.processed_at = datetime.now(timezone.utc)
                failed += 1
            else:
                backoff_minutes = 2 ** item.attempts
                item.status = "pending"
                item.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=backoff_minutes)
            db.commit()

    return {
        "processed": dispatched + failed + cancelled,
        "dispatched": dispatched,
        "failed": failed,
        "cancelled": cancelled,
        "halted_by_kill_switch": False,
    }


def list_outbox_items(db: Session, status_filter: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    q = db.query(OutboundDispatchOutbox).order_by(OutboundDispatchOutbox.created_at.desc())
    if status_filter and status_filter != "all":
        q = q.filter(OutboundDispatchOutbox.status == status_filter)
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id,
            "channel": r.channel,
            "entity_id": r.entity_id,
            "campaign_id": r.campaign_id,
            "idempotency_key": r.idempotency_key,
            "status": r.status,
            "attempts": r.attempts,
            "max_attempts": r.max_attempts,
            "next_retry_at": r.next_retry_at.isoformat() if r.next_retry_at else None,
            "last_error": r.last_error,
            "result_summary": r.result_summary,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "processed_at": r.processed_at.isoformat() if r.processed_at else None,
        }
        for r in rows
    ]
