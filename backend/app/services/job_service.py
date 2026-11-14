import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.job import BackgroundTaskRecord, DeadLetterTask, TASK_CATEGORIES, TASK_STATUSES

logger = logging.getLogger(__name__)

# In-memory rate limiting fallback if Redis is unavailable
_LOCAL_RATE_LIMITS: Dict[str, List[float]] = {}


def get_redis_client():
    """Attempt to connect to Redis, returning None if unreachable or disabled."""
    try:
        import redis
        client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1.0)
        client.ping()
        return client
    except Exception as e:
        logger.debug(f"Redis not available for direct client connection: {e}")
        return None


def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """
    Token/sliding-window rate limiter using Redis if available, with in-memory fallback.
    Returns True if allowed, False if rate limit exceeded.
    """
    now = time.time()
    r = get_redis_client()
    if r:
        try:
            pipe = r.pipeline()
            redis_key = f"rate_limit:{key}"
            # Remove timestamps outside current window
            pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
            # Count remaining items
            pipe.zcard(redis_key)
            # Add current timestamp
            pipe.zadd(redis_key, {str(now): now})
            # Set expiry on key
            pipe.expire(redis_key, window_seconds + 5)
            results = pipe.execute()
            count = results[1]
            if count >= limit:
                return False
            return True
        except Exception as e:
            logger.warning(f"Redis rate limiting error, falling back to local: {e}")

    # Local fallback
    history = _LOCAL_RATE_LIMITS.setdefault(key, [])
    # Clean up old timestamps
    _LOCAL_RATE_LIMITS[key] = [t for t in history if t > now - window_seconds]
    if len(_LOCAL_RATE_LIMITS[key]) >= limit:
        return False
    _LOCAL_RATE_LIMITS[key].append(now)
    return True


def create_background_task(
    db: Session,
    category: str,
    payload: Dict[str, Any],
    idempotency_key: Optional[str] = None,
    campaign_id: Optional[int] = None,
    company_id: Optional[int] = None,
    max_retries: int = 3,
    execute_sync: bool = False
) -> BackgroundTaskRecord:
    """
    Creates and records a background job. Checks idempotency.
    Triggers Celery worker task or executes synchronously if requested.
    """
    if category not in TASK_CATEGORIES:
        raise ValueError(f"Invalid category '{category}'. Must be one of {TASK_CATEGORIES}")

    # Idempotency check: if already processed or in progress, return existing
    if idempotency_key:
        existing = db.query(BackgroundTaskRecord).filter(
            BackgroundTaskRecord.idempotency_key == idempotency_key
        ).first()
        if existing:
            if existing.status in ["completed", "running", "pending"]:
                logger.info(f"Duplicate job skipped due to idempotency key {idempotency_key} (status: {existing.status})")
                return existing

    task_uuid = str(uuid.uuid4())
    payload_str = json.dumps(payload, default=str)

    task_record = BackgroundTaskRecord(
        task_id=task_uuid,
        category=category,
        idempotency_key=idempotency_key,
        status="pending",
        payload_json=payload_str,
        max_retries=max_retries,
        retry_count=0,
        campaign_id=campaign_id,
        company_id=company_id,
        created_at=datetime.now(timezone.utc)
    )
    db.add(task_record)
    db.commit()
    db.refresh(task_record)

    # Dispatch to Celery or run synchronous
    if execute_sync:
        _run_task_synchronously(task_record.id, category, payload, db=db)
        db.refresh(task_record)
    else:
        try:
            from app.worker.tasks import dispatch_celery_task
            dispatch_celery_task(category, task_uuid, payload)
        except Exception as e:
            logger.warning(f"Could not dispatch via Celery ({e}); executing task directly.")
            _run_task_synchronously(task_record.id, category, payload, db=db)
            db.refresh(task_record)

    return task_record


def _run_task_synchronously(task_record_id: int, category: str, payload: Dict[str, Any], db: Optional[Session] = None):
    """Execute task synchronously as a reliable fallback."""
    from app.worker.tasks import execute_task_logic
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        record = db.query(BackgroundTaskRecord).filter(BackgroundTaskRecord.id == task_record_id).first()
        if not record:
            return
        record.status = "running"
        record.started_at = datetime.now(timezone.utc)
        db.commit()

        result = execute_task_logic(category, payload, db=db)

        record.status = "completed"
        record.result_json = json.dumps(result, default=str)
        record.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        logger.error(f"Synchronous execution failed for {category}: {exc}", exc_info=True)
        record = db.query(BackgroundTaskRecord).filter(BackgroundTaskRecord.id == task_record_id).first()
        if record:
            record.status = "failed"
            record.error_message = str(exc)
            record.completed_at = datetime.now(timezone.utc)
            db.commit()
            # Insert to dead letter queue
            dlq = DeadLetterTask(
                task_id=record.task_id,
                category=category,
                idempotency_key=record.idempotency_key,
                payload_json=record.payload_json,
                final_error=str(exc),
                retries_exhausted=record.retry_count,
                failed_at=datetime.now(timezone.utc)
            )
            db.add(dlq)
            db.commit()
    finally:
        if should_close:
            db.close()


def cancel_background_task(db: Session, task_id: str) -> bool:
    """Cancels a pending or running background task."""
    record = db.query(BackgroundTaskRecord).filter(BackgroundTaskRecord.task_id == task_id).first()
    if not record:
        return False
    if record.status in ["completed", "cancelled"]:
        return False

    try:
        from app.worker.celery_app import celery_app
        celery_app.control.revoke(task_id, terminate=True)
    except Exception as e:
        logger.warning(f"Failed to revoke Celery task {task_id}: {e}")

    record.status = "cancelled"
    record.completed_at = datetime.now(timezone.utc)
    db.commit()
    return True


def list_background_tasks(
    db: Session,
    category: Optional[str] = None,
    status: Optional[str] = None,
    campaign_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50
) -> Tuple[List[BackgroundTaskRecord], int]:
    """Lists background task records with filtering and pagination."""
    query = db.query(BackgroundTaskRecord)
    if category:
        query = query.filter(BackgroundTaskRecord.category == category)
    if status:
        query = query.filter(BackgroundTaskRecord.status == status)
    if campaign_id:
        query = query.filter(BackgroundTaskRecord.campaign_id == campaign_id)

    total = query.count()
    records = query.order_by(BackgroundTaskRecord.created_at.desc()).offset(skip).limit(limit).all()
    return records, total


def list_dead_letter_tasks(
    db: Session,
    skip: int = 0,
    limit: int = 50
) -> Tuple[List[DeadLetterTask], int]:
    """Lists dead letter queue tasks."""
    query = db.query(DeadLetterTask)
    total = query.count()
    items = query.order_by(DeadLetterTask.failed_at.desc()).offset(skip).limit(limit).all()
    return items, total


def retry_dead_letter_task(db: Session, dlq_id: int) -> Optional[BackgroundTaskRecord]:
    """Requeues a task from the dead-letter queue."""
    dlq_item = db.query(DeadLetterTask).filter(DeadLetterTask.id == dlq_id).first()
    if not dlq_item or dlq_item.requeued:
        return None

    payload = json.loads(dlq_item.payload_json) if dlq_item.payload_json else {}
    # Suffix idempotency key to avoid collision with original failed key
    new_idempotency_key = f"{dlq_item.idempotency_key or dlq_item.task_id}_retry_{int(time.time())}"

    new_task = create_background_task(
        db=db,
        category=dlq_item.category,
        payload=payload,
        idempotency_key=new_idempotency_key,
        max_retries=3
    )

    dlq_item.requeued = True
    db.commit()
    return new_task


def get_queue_health(db: Session) -> Dict[str, Any]:
    """Aggregates queue status, worker availability, Redis connectivity, and task counts."""
    # 1. Redis status
    redis_connected = False
    redis_ping_ms = None
    r = get_redis_client()
    if r:
        try:
            t0 = time.time()
            r.ping()
            redis_ping_ms = round((time.time() - t0) * 1000, 2)
            redis_connected = True
        except Exception:
            redis_connected = False

    # 2. Celery workers status
    active_workers = []
    try:
        from app.worker.celery_app import celery_app
        inspector = celery_app.control.inspect(timeout=1.0)
        ping_res = inspector.ping()
        if ping_res:
            active_workers = list(ping_res.keys())
    except Exception as e:
        logger.debug(f"Celery inspect failed: {e}")

    # 3. Task counts from PostgreSQL
    counts_by_status = {}
    rows = db.query(
        BackgroundTaskRecord.status,
        func.count(BackgroundTaskRecord.id)
    ).group_by(BackgroundTaskRecord.status).all()
    for status, count in rows:
        counts_by_status[status] = count

    counts_by_category = {}
    cat_rows = db.query(
        BackgroundTaskRecord.category,
        func.count(BackgroundTaskRecord.id)
    ).group_by(BackgroundTaskRecord.category).all()
    for cat, count in cat_rows:
        counts_by_category[cat] = count

    dlq_count = db.query(DeadLetterTask).filter(DeadLetterTask.requeued == False).count()

    # 4. Recent failure rate (last 24 hours)
    one_day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_total = db.query(BackgroundTaskRecord).filter(BackgroundTaskRecord.created_at >= one_day_ago).count()
    recent_failed = db.query(BackgroundTaskRecord).filter(
        BackgroundTaskRecord.created_at >= one_day_ago,
        BackgroundTaskRecord.status == "failed"
    ).count()

    failure_rate = round((recent_failed / recent_total * 100), 2) if recent_total > 0 else 0.0

    return {
        "status": "healthy" if (redis_connected or len(active_workers) > 0 or recent_failed == 0) else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "timezone": settings.TIMEZONE,
        "redis": {
            "connected": redis_connected,
            "url": settings.REDIS_URL,
            "ping_ms": redis_ping_ms
        },
        "celery": {
            "active_workers": active_workers,
            "worker_count": len(active_workers),
            "queues": ["research", "outreach", "high_priority", "default"]
        },
        "tasks": {
            "counts_by_status": counts_by_status,
            "counts_by_category": counts_by_category,
            "pending": counts_by_status.get("pending", 0),
            "running": counts_by_status.get("running", 0),
            "completed": counts_by_status.get("completed", 0),
            "failed": counts_by_status.get("failed", 0),
            "dead_letter_unresolved": dlq_count,
            "failure_rate_24h_percent": failure_rate
        }
    }
