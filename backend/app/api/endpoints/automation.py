"""
ActTrident Local Automation & Scheduler Endpoints.
Allows monitoring and control of background outreach automation, IST business hours guards,
and transactional outbox dispatching on Windows PCs.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, require_role, get_current_user
from app.models.user import User
from app.services.local_scheduler import local_scheduler
from app.core.audit import record_audit_log

router = APIRouter()


class TriggerJobRequest(BaseModel):
    job_name: str


@router.get("/status")
def get_automation_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves current scheduler status, IST time, business hour status, and recent activity logs."""
    return local_scheduler.get_status(db=db)


@router.post("/start")
def start_automation(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Starts the local persistent scheduler thread."""
    local_scheduler.start()
    record_audit_log(
        db=db,
        action="automation_started",
        entity_type="scheduler",
        entity_id="local_scheduler",
        user_id=current_user.id,
        details={"status": "running"},
    )
    return local_scheduler.get_status(db=db)


@router.post("/stop")
def stop_automation(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Stops the local persistent scheduler thread."""
    local_scheduler.stop()
    record_audit_log(
        db=db,
        action="automation_stopped",
        entity_type="scheduler",
        entity_id="local_scheduler",
        user_id=current_user.id,
        details={"status": "stopped"},
    )
    return local_scheduler.get_status(db=db)


@router.post("/pause")
def pause_automation(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Pauses running jobs without shutting down the scheduler loop."""
    local_scheduler.pause()
    record_audit_log(
        db=db,
        action="automation_paused",
        entity_type="scheduler",
        entity_id="local_scheduler",
        user_id=current_user.id,
        details={"status": "paused"},
    )
    return local_scheduler.get_status(db=db)


@router.post("/resume")
def resume_automation(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Resumes paused scheduler jobs."""
    local_scheduler.resume()
    record_audit_log(
        db=db,
        action="automation_resumed",
        entity_type="scheduler",
        entity_id="local_scheduler",
        user_id=current_user.id,
        details={"status": "resumed"},
    )
    return local_scheduler.get_status(db=db)


@router.post("/trigger-job")
def trigger_job_endpoint(
    req: TriggerJobRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Immediately triggers an automation job synchronously."""
    valid_jobs = ["outbox_dispatch", "followup_evaluation", "inbox_sync", "nightly_discovery_research", "database_backup"]
    if req.job_name not in valid_jobs:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid job name '{req.job_name}'. Valid jobs: {valid_jobs}",
        )

    res = local_scheduler.trigger_job(req.job_name)
    record_audit_log(
        db=db,
        action="scheduler_job_triggered",
        entity_type="scheduler_job",
        entity_id=req.job_name,
        user_id=current_user.id,
        details={"job": req.job_name, "result": res},
    )
    return {"job": req.job_name, "result": res, "scheduler_status": local_scheduler.get_status(db=db)}
