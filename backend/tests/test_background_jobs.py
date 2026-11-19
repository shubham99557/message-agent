import time
from app.models.job import BackgroundTaskRecord, DeadLetterTask
from app.services import job_service


def test_job_idempotency_prevents_duplicate_dispatch(db):
    """Ensure submitting a job with the same idempotency key returns the existing record."""
    key = f"test_idemp_{int(time.time() * 1000)}"
    payload = {"cities": ["Siliguri"]}

    task1 = job_service.create_background_task(
        db=db,
        category="company_discovery",
        payload=payload,
        idempotency_key=key,
        execute_sync=True
    )
    assert task1.id is not None
    assert task1.status == "completed"

    # Second submission with the same idempotency key
    task2 = job_service.create_background_task(
        db=db,
        category="company_discovery",
        payload=payload,
        idempotency_key=key,
        execute_sync=True
    )
    # Must be the exact same record
    assert task2.id == task1.id
    assert task2.task_id == task1.task_id

    # Verify only 1 record exists in DB
    total = db.query(BackgroundTaskRecord).filter(BackgroundTaskRecord.idempotency_key == key).count()
    assert total == 1


def test_rate_limiter_enforcement():
    """Verify rate limiter blocks excessive requests within the rate limit window."""
    rate_key = f"test_limiter_{time.time()}"
    limit = 3
    window = 10

    # First 3 should pass
    assert job_service.check_rate_limit(rate_key, limit=limit, window_seconds=window) is True
    assert job_service.check_rate_limit(rate_key, limit=limit, window_seconds=window) is True
    assert job_service.check_rate_limit(rate_key, limit=limit, window_seconds=window) is True

    # 4th should be blocked by rate limit
    assert job_service.check_rate_limit(rate_key, limit=limit, window_seconds=window) is False


def test_synchronous_task_execution_categories(db, test_company):
    """Test execution logic for various task categories."""
    # 1. Company discovery
    task_disc = job_service.create_background_task(
        db=db,
        category="company_discovery",
        payload={"cities": ["Siliguri", "Gangtok"]},
        execute_sync=True
    )
    assert task_disc.status == "completed"
    assert task_disc.result_json is not None

    # 2. Lead qualification
    task_qual = job_service.create_background_task(
        db=db,
        category="lead_qualification",
        payload={"company_id": test_company.id},
        execute_sync=True
    )
    assert task_qual.status == "completed"
    assert "score" in task_qual.result_json

    # 3. Daily reporting
    task_rep = job_service.create_background_task(
        db=db,
        category="daily_reporting",
        payload={},
        execute_sync=True
    )
    assert task_rep.status == "completed"
    assert "metrics" in task_rep.result_json


def test_task_cancellation(db):
    """Test cancelling a background task record."""
    task = job_service.create_background_task(
        db=db,
        category="followup_scheduling",
        payload={},
        execute_sync=False
    )
    # Cancel the task
    cancelled = job_service.cancel_background_task(db, task.task_id)
    assert cancelled is True

    db.refresh(task)
    assert task.status == "cancelled"
    assert task.completed_at is not None


def test_dead_letter_queue_and_retry(db):
    """Test that failed tasks get logged to the Dead Letter Queue and can be retried."""
    dlq_idemp = f"dlq_test_{time.time()}"
    # Trigger a task with an invalid/failing payload
    task = job_service.create_background_task(
        db=db,
        category="crm_update",
        payload={"lead_id": 999999},  # Non-existent lead will cause controlled error or failure
        idempotency_key=dlq_idemp,
        execute_sync=True
    )
    assert task.status == "completed"  # execute_task_logic returns {'error': ...}

    # Simulate an actual unhandled exception causing DLQ insertion
    fake_dlq = DeadLetterTask(
        task_id="failed_task_uuid_123",
        category="email_dispatch",
        idempotency_key="failed_key_123",
        payload_json='{"draft_id": 9999}',
        final_error="SMTP connection timeout after 3 retries",
        retries_exhausted=3
    )
    db.add(fake_dlq)
    db.commit()
    db.refresh(fake_dlq)

    # Requeue from DLQ
    requeued_task = job_service.retry_dead_letter_task(db, fake_dlq.id)
    assert requeued_task is not None
    assert requeued_task.category == "email_dispatch"

    db.refresh(fake_dlq)
    assert fake_dlq.requeued is True


def test_queue_health_endpoint(client, auth_headers):
    """Ensure authenticated users can view queue health and task metrics."""
    res = client.get("/api/v1/jobs/health", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "timezone" in data
    assert data["timezone"] == "Asia/Kolkata"
    assert "tasks" in data
    assert "redis" in data
    assert "celery" in data


def test_jobs_rbac_permissions(client, auth_headers, admin_auth_headers):
    """Verify sales reps cannot trigger tasks or access dead letter queue, but admins can."""
    trigger_payload = {
        "category": "company_discovery",
        "payload": {"cities": ["Patna"]},
        "execute_sync": True
    }

    # Sales rep attempt to trigger -> 403 Forbidden
    res_sales = client.post("/api/v1/jobs/trigger", json=trigger_payload, headers=auth_headers)
    assert res_sales.status_code == 403

    # Admin attempt to trigger -> 202 Accepted
    res_admin = client.post("/api/v1/jobs/trigger", json=trigger_payload, headers=admin_auth_headers)
    assert res_admin.status_code == 202
    created_task = res_admin.json()
    assert created_task["category"] == "company_discovery"

    # Sales rep cannot view dead letter queue -> 403
    res_dlq_sales = client.get("/api/v1/jobs/dead-letter", headers=auth_headers)
    assert res_dlq_sales.status_code == 403

    # Admin can view dead letter queue -> 200
    res_dlq_admin = client.get("/api/v1/jobs/dead-letter", headers=admin_auth_headers)
    assert res_dlq_admin.status_code == 200
    assert isinstance(res_dlq_admin.json(), list)
