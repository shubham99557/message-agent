import os
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "acttrident_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks"]
)

# Celery Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.TIMEZONE,  # Asia/Kolkata
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3000,
    worker_prefetch_multiplier=1,  # Fair task distribution for rate limiting
    worker_max_tasks_per_child=1000,  # Prevent memory leaks
    task_acks_late=True,  # Acknowledge task only after completion (fault-tolerant)
    task_reject_on_worker_lost=True,  # Requeue task if worker crashes
)

# Task Queue Routing
celery_app.conf.task_routes = {
    "app.worker.tasks.task_company_discovery": {"queue": "research"},
    "app.worker.tasks.task_company_enrichment": {"queue": "research"},
    "app.worker.tasks.task_website_research": {"queue": "research"},
    "app.worker.tasks.task_lead_qualification": {"queue": "default"},
    "app.worker.tasks.task_email_generation": {"queue": "default"},
    "app.worker.tasks.task_whatsapp_generation": {"queue": "default"},
    "app.worker.tasks.task_email_dispatch": {"queue": "outreach"},
    "app.worker.tasks.task_whatsapp_dispatch": {"queue": "outreach"},
    "app.worker.tasks.task_reply_ingestion": {"queue": "high_priority"},
    "app.worker.tasks.task_reply_classification": {"queue": "high_priority"},
    "app.worker.tasks.task_crm_update": {"queue": "default"},
    "app.worker.tasks.task_followup_scheduling": {"queue": "default"},
    "app.worker.tasks.task_daily_reporting": {"queue": "default"},
    "app.worker.tasks.task_outbox_dispatch": {"queue": "outreach"},
    "app.worker.tasks.task_gmail_reply_sync": {"queue": "high_priority"},
}

# Celery Beat Periodic Automation Schedule (Asia/Kolkata Timezone)
celery_app.conf.beat_schedule = {
    # 1. Daily automated company discovery (01:00 AM IST — strictly real public sources, never demo fixtures)
    "nightly-company-discovery": {
        "task": "app.worker.tasks.task_company_discovery",
        "schedule": crontab(hour=1, minute=0),
        "args": [{"cities": ["Siliguri", "Gangtok", "Patna", "Bhagalpur"]}],
    },
    # 2. Daily automated stale evidence re-verification (04:00 AM IST)
    "daily-stale-lead-verification": {
        "task": "app.worker.tasks.task_lead_qualification",
        "schedule": crontab(hour=4, minute=0),
        "args": [{"recheck_stale_only": True}],
    },
    # 3. Morning business day digest & operational reporting (09:00 AM IST)
    "daily-morning-reporting-digest": {
        "task": "app.worker.tasks.task_daily_reporting",
        "schedule": crontab(hour=9, minute=0),
        "args": [],
    },
    # 4. Business hours autonomous follow-up engine (09:30 - 17:30 IST, Mon-Fri — strictly within 09:00-18:00 IST)
    "business-hours-followup-scheduler": {
        "task": "app.worker.tasks.task_followup_scheduling",
        "schedule": crontab(minute=30, hour="9-17", day_of_week="mon-fri"),
        "args": [],
    },
    # 5. Transactional Outbox Processor (Every 2 minutes — respects Kill Switch & campaign pause/stop)
    "transactional-outbox-processor": {
        "task": "app.worker.tasks.task_outbox_dispatch",
        "schedule": crontab(minute="*/2"),
        "args": [{"limit": 20}],
    },
    # 6. Gmail Reply & Bounce Synchronization (Every 5 minutes when Gmail OAuth is connected)
    "gmail-reply-sync-poller": {
        "task": "app.worker.tasks.task_gmail_reply_sync",
        "schedule": crontab(minute="*/5"),
        "args": [{"max_results": 25}],
    },
}
