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

    def trigger_job(self, job_name: str) -> Dict[str, Any]:
        """Executes a specific automation task synchronously or as part of the scheduled loop."""
        now = datetime.now(timezone.utc)
        self.last_run[job_name] = now

        db = SessionLocal()
        try:
            if job_name == "outbox_dispatch":
                return self._job_outbox_dispatch(db)
            elif job_name == "followup_evaluation":
                return self._job_followup_evaluation(db)
            elif job_name == "inbox_sync":
                return self._job_inbox_sync(db)
            elif job_name == "nightly_discovery_research":
                return self._job_nightly_discovery(db)
            elif job_name == "database_backup":
                return self._job_database_backup()
            else:
                raise ValueError(f"Unknown scheduler job: {job_name}")
        except Exception as exc:
            self.task_stats["errors"] += 1
            self._log_event(job_name, "failed", str(exc))
            return {"job": job_name, "status": "failed", "error": str(exc)}
        finally:
            db.close()

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
            "recent_events": self.execution_log[:15],
        }


# Global singleton instance
local_scheduler = LocalScheduler()
