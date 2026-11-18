from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User
from app.schemas.job import (
    BackgroundTaskResponse,
    BackgroundTaskTriggerRequest,
    DeadLetterTaskResponse,
    QueueHealthResponse
)
from app.services import job_service
from app.services.orchestration_service import list_outbox_items, process_outbox_batch

router = APIRouter()


@router.get("/health", response_model=QueueHealthResponse)
def get_queue_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns background queue health, Redis status, Celery worker ping, and task metrics."""
    return job_service.get_queue_health(db)


@router.get("/history", response_model=List[BackgroundTaskResponse])
def get_task_history(
    category: Optional[str] = None,
    status: Optional[str] = None,
    campaign_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves paginated background task execution records."""
    records, _ = job_service.list_background_tasks(
        db, category=category, status=status, campaign_id=campaign_id, skip=skip, limit=limit
    )
    return records


@router.post("/trigger", response_model=BackgroundTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_background_task(
    req: BackgroundTaskTriggerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Manually triggers an autonomous background task (Admin/Manager only)."""
    try:
        task = job_service.create_background_task(
            db=db,
            category=req.category,
            payload=req.payload or {},
            idempotency_key=req.idempotency_key,
            campaign_id=req.campaign_id,
            company_id=req.company_id,
            execute_sync=req.execute_sync
        )
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cancel/{task_id}")
def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Cancels a pending or active background task."""
    success = job_service.cancel_background_task(db, task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or already completed/cancelled")
    return {"message": f"Task {task_id} successfully cancelled"}


@router.get("/dead-letter", response_model=List[DeadLetterTaskResponse])
def get_dead_letter_queue(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Lists dead-letter queue records for exhausted retry failures."""
    dlq_items, _ = job_service.list_dead_letter_tasks(db, skip=skip, limit=limit)
    return dlq_items


@router.post("/dead-letter/{dlq_id}/retry", response_model=BackgroundTaskResponse)
def retry_dead_letter_task(
    dlq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Requeues a failed task from the dead-letter queue with a fresh task identifier."""
    task = job_service.retry_dead_letter_task(db, dlq_id)
    if not task:
        raise HTTPException(status_code=404, detail="Dead letter task not found or already requeued")
    return task


@router.get("/outbox")
def get_dispatch_outbox(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Lists transactional OutboundDispatchOutbox items."""
    return list_outbox_items(db=db, status_filter=status_filter, limit=limit)


@router.post("/outbox/process")
def process_dispatch_outbox(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Processes pending transactional OutboundDispatchOutbox records respecting kill switch and campaign status."""
    return process_outbox_batch(db=db, user_id=current_user.id, limit=limit)
