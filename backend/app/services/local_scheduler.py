"""
ActTrident Local-First Persistent Windows Scheduler.

Runs in a robust background daemon thread without requiring Celery, Redis, or cloud services.
Executes periodic outreach tasks strictly during IST business hours (09:00 - 18:00 IST),
processes transactional outbox items, synchronizes inbox replies, and creates local backups.
"""

import threading
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from app.core.database import SessionLocal
from app.core.config import settings
from app.core.storage import get_acttrident_data_dir, create_database_backup
from app.services.orchestration_service import (
    is_kill_switch_active,
    is_within_ist_business_hours,
    process_outbox_batch,
    IST_OFFSET,
)

logger = logging.getLogger("acttrident.scheduler")


class LocalScheduler:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.is_running = False
        self.is_paused = False

        self.last_run: Dict[str, Optional[datetime]] = {
            "outbox_dispatch": None,
            "followup_evaluation": None,
            "inbox_sync": None,
            "nightly_discovery_research": None,
            "database_backup": None,
        }

        self.intervals_sec: Dict[str, int] = {
            "outbox_dispatch": 60,            # 1 minute
            "followup_evaluation": 900,       # 15 minutes
            "inbox_sync": 300,                 # 5 minutes
            "nightly_discovery_research": 86400, # 24 hours
            "database_backup": 86400,          # 24 hours
        }

        self.task_stats: Dict[str, int] = {
            "outbox_dispatched": 0,
            "outbox_failed": 0,
            "followups_evaluated": 0,
            "replies_synced": 0,
            "backups_created": 0,
            "total_cycles": 0,
            "errors": 0,
        }

        self.execution_log: List[Dict[str, Any]] = []

    def load_persisted_state(self, db=None):
        """Loads durable last_run timestamps from SQLite SchedulerJobRecord table."""
        try:
            session = db or SessionLocal()
            try:
                from app.models.orchestration import SchedulerJobRecord
                records = session.query(SchedulerJobRecord).all()
                for rec in records:
                    if rec.job_name in self.last_run and rec.last_run_at:
                        dt = rec.last_run_at
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        self.last_run[rec.job_name] = dt
            finally:
                if not db:
                    session.close()
        except Exception as exc:
            logger.debug(f"Could not load persisted scheduler state: {exc}")

    def _persist_job_run(self, db, job_name: str, status: str, detail: Optional[str] = None, error: Optional[str] = None):
        """Updates SchedulerJobRecord and logs to SchedulerExecutionHistory in SQLite."""
        try:
            from app.models.orchestration import SchedulerJobRecord, SchedulerExecutionHistory
            now = datetime.now(timezone.utc)
            rec = db.query(SchedulerJobRecord).filter(SchedulerJobRecord.job_name == job_name).first()
            if not rec:
                rec = SchedulerJobRecord(
                    job_name=job_name,
                    interval_seconds=self.intervals_sec.get(job_name, 60),
                )
                db.add(rec)
            rec.last_run_at = now
            rec.last_status = status
            rec.total_runs = (rec.total_runs or 0) + 1
            if status in ("success", "executed"):
                rec.last_success_at = now
                rec.last_error = None
            elif error:
                rec.last_error = str(error)[:500]

            hist = SchedulerExecutionHistory(
                job_name=job_name,
                status=status,
                detail=detail or (f"Error: {error}" if error else None),
                created_at=now,
            )
            db.add(hist)
            db.commit()
        except Exception as exc:
            logger.debug(f"Could not persist scheduler job record: {exc}")

    def _log_event(self, job_name: str, status: str, detail: str):
        event = {
            "job": job_name,
            "status": status,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.execution_log.insert(0, event)
        if len(self.execution_log) > 50:
            self.execution_log.pop()
        logger.info(f"[SCHEDULER] {job_name} ({status}): {detail}")

    def start(self):
        if self.is_running:
            return
        self.load_persisted_state()
        self._stop_event.clear()
        self.is_running = True
        self.is_paused = False
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="ActTrident-Scheduler")
        self._thread.start()
        self._log_event("scheduler", "started", "Persistent background scheduler thread initialized.")

    def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._log_event("scheduler", "stopped", "Scheduler stopped by operator.")

    def pause(self):
        self.is_paused = True
        self._log_event("scheduler", "paused", "Scheduler paused. Running jobs suspended.")

    def resume(self):
        self.is_paused = False
        self._log_event("scheduler", "resumed", "Scheduler resumed normal operation.")

    def _worker_loop(self):
        logger.info("ActTrident Persistent Local Scheduler worker loop running.")
        while not self._stop_event.is_set():
            try:
                if not self.is_paused:
                    self._check_and_run_due_jobs()
            except Exception as exc:
                self.task_stats["errors"] += 1
                logger.error(f"Scheduler worker loop error: {exc}", exc_info=True)
                self._log_event("worker_loop", "error", str(exc))

            # Sleep 5 seconds between evaluations to remain responsive to stop/pause
            for _ in range(5):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

        self.is_running = False
        logger.info("ActTrident Persistent Local Scheduler thread terminated.")

    def _check_and_run_due_jobs(self):
        now = datetime.now(timezone.utc)
        self.task_stats["total_cycles"] += 1

        for job_name, interval in self.intervals_sec.items():
            last = self.last_run.get(job_name)
            if not last or (now - last).total_seconds() >= interval:
                self.trigger_job(job_name)

    def trigger_job(self, job_name: str, db=None) -> Dict[str, Any]:
        """Executes a specific automation task synchronously or as part of the scheduled loop."""
        now = datetime.now(timezone.utc)
        self.last_run[job_name] = now

        session = db or SessionLocal()
        try:
            res: Dict[str, Any] = {}
            if job_name == "outbox_dispatch":
                res = self._job_outbox_dispatch(session)
            elif job_name == "followup_evaluation":
                res = self._job_followup_evaluation(session)
            elif job_name == "inbox_sync":
                res = self._job_inbox_sync(session)
            elif job_name == "nightly_discovery_research":
                res = self._job_nightly_discovery(session)
            elif job_name == "database_backup":
                res = self._job_database_backup()
            else:
                raise ValueError(f"Unknown scheduler job: {job_name}")

            job_status = res.get("status", "executed")
            detail_msg = str(res.get("reason") or res.get("backup_file") or f"Executed successfully")
            self._persist_job_run(session, job_name, status=job_status, detail=detail_msg)
            return res
        except Exception as exc:
            self.task_stats["errors"] += 1
            self._log_event(job_name, "failed", str(exc))
            self._persist_job_run(session, job_name, status="failed", error=str(exc))
            return {"job": job_name, "status": "failed", "error": str(exc)}
        finally:
            if not db:
                session.close()

    def _job_outbox_dispatch(self, db) -> Dict[str, Any]:
        ks_active, ks_reason = is_kill_switch_active(db)
        if ks_active:
            self._log_event("outbox_dispatch", "blocked", f"Kill switch active: {ks_reason}")
            return {"status": "blocked_kill_switch", "reason": ks_reason}

        res = process_outbox_batch(db, user_id=1, limit=25)
        dispatched = res.get("dispatched", 0)
        failed = res.get("failed", 0)
        self.task_stats["outbox_dispatched"] += dispatched
        self.task_stats["outbox_failed"] += failed

        if dispatched > 0 or failed > 0:
            self._log_event("outbox_dispatch", "executed", f"Dispatched {dispatched}, Failed {failed}")
        return res

    def _job_followup_evaluation(self, db) -> Dict[str, Any]:
        # Respect Asia/Kolkata business hours (09:00 - 18:00 IST)
        within_hours, reason = is_within_ist_business_hours()
        if not within_hours:
            return {"status": "skipped_outside_business_hours", "reason": reason}

        from app.services.followup_service import process_autonomous_followups
        res = process_autonomous_followups(db)
        evaluated = res.get("evaluated_count", 0)
        self.task_stats["followups_evaluated"] += evaluated
        if evaluated > 0:
            self._log_event("followup_evaluation", "executed", f"Evaluated {evaluated} leads for follow-up")
        return res

    def _job_inbox_sync(self, db) -> Dict[str, Any]:
        from app.integrations.gmail_adapter import get_active_gmail_connection, sync_gmail_replies
        conn = get_active_gmail_connection(db)
        if not conn or conn.status != "connected":
            return {"status": "skipped_disconnected", "synced_replies": 0}

        res = sync_gmail_replies(db=db, connection=conn, max_results=20)
        synced = res.get("synced_replies", 0)
        self.task_stats["replies_synced"] += synced
        if synced > 0:
            self._log_event("inbox_sync", "executed", f"Synced {synced} new incoming replies")
        return res

    def _job_nightly_discovery(self, db) -> Dict[str, Any]:
        from app.services.autonomous_agent_service import ensure_verified_targets
        companies = ensure_verified_targets(db, target_city=None, max_discover=10)
        self._log_event("nightly_discovery_research", "executed", f"Refreshed {len(companies)} targets in directory.")
        return {"status": "success", "targets_count": len(companies)}

    def _job_database_backup(self) -> Dict[str, Any]:
        backup_info = create_database_backup()
        self.task_stats["backups_created"] += 1
        self._log_event("database_backup", "executed", f"Backup created: {backup_info.get('backup_file')}")
        return backup_info

    def get_status(self, db=None) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        ist_now = now.astimezone(IST_OFFSET)
        is_ist_hours, ist_msg = is_within_ist_business_hours(now)

        ks_active = False
        ks_reason = None
        if db:
            ks_active, ks_reason = is_kill_switch_active(db)

        next_runs = {}
        for job_name, interval in self.intervals_sec.items():
            last = self.last_run.get(job_name)
            if last:
                next_dt = last + timedelta(seconds=interval)
                next_runs[job_name] = next_dt.isoformat()
            else:
                next_runs[job_name] = "immediately_due"

        recent_events = self.execution_log[:15]
        if db:
            try:
                from app.models.orchestration import SchedulerExecutionHistory
                db_hist = (
                    db.query(SchedulerExecutionHistory)
                    .order_by(SchedulerExecutionHistory.created_at.desc())
                    .limit(15)
                    .all()
                )
                if db_hist:
                    recent_events = [
                        {
                            "job": h.job_name,
                            "status": h.status,
                            "detail": h.detail,
                            "timestamp": h.created_at.isoformat() if h.created_at else "",
                        }
                        for h in db_hist
                    ]
            except Exception:
                pass

        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "ist_time": ist_now.strftime("%Y-%m-%d %H:%M:%S IST"),
            "is_within_ist_business_hours": is_ist_hours,
            "business_hours_status": ist_msg,
            "kill_switch_active": ks_active,
            "kill_switch_reason": ks_reason,
            "last_run": {k: v.isoformat() if v else None for k, v in self.last_run.items()},
            "next_run": next_runs,
            "intervals_sec": self.intervals_sec,
            "task_stats": self.task_stats,
            "recent_events": recent_events,
        }


# Global singleton instance
local_scheduler = LocalScheduler()
