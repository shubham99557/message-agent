# Production Gap Analysis & Technical Inventory

**Project**: ActTrident AI Sales Outreach & Automation Platform  
**Target Architecture**: Fast-API backend, React 19 / TypeScript / Vite frontend, Celery & Celery Beat background workers, Redis message broker, PostgreSQL 18 datastore.  
**Audited Revision**: `c42f69b` + Hardening Enhancements  
**Branch**: `feature/production-audit-and-hardening`

---

## 1. Executive Summary

This independent production gap analysis was conducted against the ActTrident repository to evaluate system stability, security perimeter integrity, role-based access controls (RBAC), multi-channel messaging semantics, transactional reliability, and deployment preparedness.

A total of 14 critical-to-medium gaps were audited and verified. All technical gaps have been resolved, verified with regression tests, and confirmed without introducing architectural breaking changes.

---

## 2. Comprehensive Inventory of Audited Gaps & Solutions

### GAP-01: Broken Celery Email Dispatch Import & Signature
- **Component**: Celery Task Execution (`app.tasks.email_tasks`)
- **Severity**: Critical (P0)
- **Problem**: `send_email_task` imported nonexistent modules and lacked the required `user_id` and database session initialization needed for transactional sending.
- **Recommended Solution**: Re-wire `send_email_task` to obtain an isolated database session and call `send_approved_email(db, draft_id, user_id=None)` with robust exception handling and DLQ recording.
- **Affected Files**: `backend/app/tasks/email_tasks.py`, `backend/app/services/email_sender_service.py`
- **Tests Required**: `backend/tests/test_blocker_remediation.py::test_celery_email_dispatch_signature`
- **Verification Evidence**: Test passes synchronously and within Celery task runner.

### GAP-02: Quarantine & Isolation of Synthetic Demo Data
- **Component**: Lead Discovery & Enrichment (`app.services.discovery_service`)
- **Severity**: High (P1)
- **Problem**: Nightly discovery routine inadvertently persisted synthetic mock fixture companies (`.example.com`) directly into active CRM pipelines.
- **Recommended Solution**: Enforce an automated quarantine filter: any prospect bearing an `.example.com` domain or synthetic markers must have `is_demo=True` and `verification_status="demo_fixture"`. Block demo records from campaign recipient insertion (`HTTP 400 Bad Request`).
- **Affected Files**: `backend/app/services/discovery_service.py`, `backend/app/api/endpoints/campaigns.py`
- **Tests Required**: `backend/tests/test_blocker_remediation.py::test_demo_domain_quarantined_and_blocked_from_campaigns`
- **Verification Evidence**: Synthetic prospects are strictly partitioned; attempts to attach them to live campaigns return 400.

### GAP-03: Celery Beat Outbox & Gmail Reply Schedule Gap
- **Component**: Background Automation (`app.core.celery_app`)
- **Severity**: High (P1)
- **Problem**: Transactional outbox items and Gmail inbox replies were not registered in Celery Beat schedules, leading to stalled deliveries if manual endpoints were not triggered.
- **Recommended Solution**: Register `process-transactional-outbox` every 60 seconds and `sync-gmail-inbox-replies` every 300 seconds (5 minutes) in `beat_schedule`.
- **Affected Files**: `backend/app/core/celery_app.py`, `backend/app/tasks/orchestration_tasks.py`
- **Tests Required**: `backend/tests/test_blocker_remediation.py::test_celery_beat_schedule_configured`
- **Verification Evidence**: Celery Beat configuration verified; tasks run on schedule without starvation.

### GAP-04: Broken WhatsApp Channel Adapter Methods & Mock Discrepancy
- **Component**: Meta WhatsApp Cloud Integration (`app.integrations.whatsapp_adapter`)
- **Severity**: High (P1)
- **Problem**: `WhatsAppChannelAdapter` contained mismatched parameter signatures and lacked explicit simulation logging, risking confusion between sandbox and genuine deliveries.
- **Recommended Solution**: Implement complete signature alignment for template verification, outbound messaging, webhook HMAC signature validation, and explicit `simulated` vs `sent` delivery receipts.
- **Affected Files**: `backend/app/integrations/whatsapp_adapter.py`, `backend/app/services/whatsapp_service.py`
- **Tests Required**: `backend/tests/test_blocker_remediation.py::test_whatsapp_channel_adapter_and_sandbox_logging`
- **Verification Evidence**: Mock and live paths accurately return status `simulated` when credentials are in sandbox mode and `sent` only when Meta Graph API returns `wamid`.

### GAP-05: Analytics Conflation of Simulated and Genuinely Sent Outreach
- **Component**: Funnel Metrics & Dashboards (`app.services.analytics_service`)
- **Severity**: High (P1)
- **Problem**: Simulated outreach events and demo companies inflated sent message totals, skewing conversion rates and reply ratios.
- **Recommended Solution**: Enforce strict query filters: exclude `is_demo=True` companies, compute genuine messages via `EmailSendAttempt.status == 'sent'`, separate `simulated_count`, and calculate reply ratios exclusively against real deliveries.
- **Affected Files**: `backend/app/services/analytics_service.py`, `backend/app/schemas/analytics.py`
- **Tests Required**: `backend/tests/test_blocker_remediation.py::test_analytics_metrics_separation`
- **Verification Evidence**: Dashboard returns discrete fields: `emails_sent`, `emails_simulated`, `delivery_rate`, and `reply_rate` with demo data strictly filtered out.

### GAP-06: Gmail Bounce Event Deduplication
- **Component**: Inbound Bounce Synchronization (`app.services.email_sender_service`)
- **Severity**: Medium (P2)
- **Problem**: Repeated Gmail synchronization cycles re-processed the same bounce notices, recording duplicate delivery events and skewing bounce rates.
- **Recommended Solution**: Maintain a persistent registry check on `provider_message_id` and bounce timestamps; ignore duplicate bounce notifications idempotently.
- **Affected Files**: `backend/app/services/email_sender_service.py`, `backend/app/integrations/gmail_adapter.py`
- **Tests Required**: `backend/tests/test_blocker_remediation.py::test_gmail_bounce_deduplication`
- **Verification Evidence**: Multiple synchronization calls on identical bounce IDs record exactly one `bounced` event.

### GAP-07: Burst & Daily Outbound Rate Limiting
- **Component**: Sending Governance (`app.services.email_sender_service`, `app.services.whatsapp_service`)
- **Severity**: High (P1)
- **Problem**: Rapid batch sends could exceed SMTP or Meta Cloud API limits, triggering provider throttling or domain reputation penalties.
- **Recommended Solution**: Implement dual rate-limit checks: per-minute sliding window (burst limit: 10/min) and daily cumulative limit (50 emails/day, 20 WhatsApp/day) enforced on both synchronous and asynchronous paths.
- **Affected Files**: `backend/app/services/email_sender_service.py`, `backend/app/services/orchestration_service.py`
- **Tests Required**: `backend/tests/test_blocker_remediation.py::test_sending_rate_limits_enforced`
- **Verification Evidence**: Sends exceeding limits immediately return `HTTP 429 Too Many Requests` or mark outbox items as rate-limited with exponential backoff.

### GAP-08: Synchronous Retry Safety & Dead Letter Queue (DLQ)
- **Component**: Job Execution & Worker Reliability (`app.services.job_service`)
- **Severity**: Medium (P2)
- **Problem**: Failed synchronous jobs crashed without recording failure states in the DLQ, making operator retry impossible.
- **Recommended Solution**: Implement exponential backoff retry handler; if max retries (3) are exhausted, persist the execution record to `DeadLetterTask` with stack trace and payload for manual inspection.
- **Affected Files**: `backend/app/services/job_service.py`, `backend/app/models/job.py`
- **Tests Required**: `backend/tests/test_blocker_remediation.py::test_synchronous_job_retry_and_dlq`
- **Verification Evidence**: Failed tasks transition to `failed` and are visible in `GET /api/v1/jobs/dlq` with replay capability.

### GAP-09: Mandatory JWT Token Version (`tv`) Claim Enforcement
- **Component**: Security & Authentication (`app.core.security`, `app.api.deps`)
- **Severity**: Critical (P0)
- **Problem**: Legacy tokens without the `tv` claim could bypass user session revocation upon password reset or role demotion.
- **Recommended Solution**: Reject any JWT token missing the `tv` claim with `HTTP 401 Unauthorized`. Check decoded `tv` against the live database record on every authenticated request.
- **Affected Files**: `backend/app/core/security.py`, `backend/app/api/deps.py`
- **Tests Required**: `backend/tests/test_blocker_remediation.py::test_jwt_mandatory_token_version_claim`
- **Verification Evidence**: Tokens without `tv` or with stale `tv` are immediately rejected with 401.

### GAP-10: Hardcoded WhatsApp Verification Token Fallbacks
- **Component**: Frontend Settings & Webhook Security (`frontend/src/views/SettingsView.tsx`)
- **Severity**: Medium (P2)
- **Problem**: Default fallback secrets were present in frontend inputs and configuration placeholders.
- **Recommended Solution**: Remove all hardcoded default tokens; require environment variables (`META_WA_VERIFY_TOKEN`) and mask tokens in the UI.
- **Affected Files**: `frontend/src/views/SettingsView.tsx`, `backend/app/core/config.py`
- **Tests Required**: `backend/tests/test_blocker_remediation.py::test_whatsapp_verify_token_secure`
- **Verification Evidence**: Webhook fails with 403 unless valid verify token matches server environment.

### GAP-11: Company & Draft Ownership Isolation
- **Component**: Multi-Tenant & RBAC Isolation (`app.api.endpoints.companies`, `app.api.endpoints.emails`)
- **Severity**: High (P1)
- **Problem**: Sales representatives could view, edit, or verify companies and drafts created by other representatives without manager oversight.
- **Recommended Solution**: Enforce strict ownership: `sales_rep` users may only modify records where `created_by_id == current_user.id`. `admin` and `manager` roles retain oversight privileges.
- **Affected Files**: `backend/app/api/endpoints/companies.py`, `backend/app/api/endpoints/emails.py`
- **Tests Required**: `backend/tests/test_blocker_remediation.py::test_company_and_draft_ownership_enforcement`
- **Verification Evidence**: Unowned edit attempts return `HTTP 403 Forbidden`.

### GAP-12: Read-Only Analyst Role (`analyst`) Implementation Gap
- **Component**: Role-Based Access Control (`app.schemas.auth`, `app.api.deps`)
- **Severity**: High (P1)
- **Problem**: System recognized `admin`, `manager`, and `sales_rep`, but lacked an explicit `analyst` role for executives or stakeholders requiring complete visibility without mutation permissions.
- **Recommended Solution**: Add `analyst` to `VALID_ROLES`. Guard all mutating endpoints across Campaigns, Companies, CRM, Outreach, Background Jobs, and Settings with `require_role(["admin", "manager", "sales_rep"])`. Allow `analyst` full read access to analytics, campaigns, companies, CRM pipeline, CSV export, approval queue, and jobs health.
- **Affected Files**: `backend/app/schemas/auth.py`, `backend/app/api/endpoints/auth.py`, `backend/app/api/endpoints/campaigns.py`, `backend/app/api/endpoints/companies.py`, `backend/app/api/endpoints/crm.py`, `backend/app/api/endpoints/emails.py`, `frontend/src/views/SettingsView.tsx`
- **Tests Required**: `backend/tests/test_analyst_rbac.py`
- **Verification Evidence**: 3 dedicated tests passing; analysts can read all views but receive 403 on create/edit/delete/dispatch.

### GAP-13: Dockerfile & Environment Path Mismatches
- **Component**: Container Packaging (`Dockerfile`, `docker-compose.yml`)
- **Severity**: Medium (P2)
- **Problem**: Frontend static distribution paths in single-container deployment did not match the FastAPI mount point, and PostgreSQL CLI tools were missing for database backup scripts.
- **Recommended Solution**: Multi-stage Dockerfile builds Vite frontend to `/app/frontend/dist`, mounts via `StaticFiles`, and installs `postgresql-client` for `pg_dump` and `pg_restore`.
- **Affected Files**: `Dockerfile`, `docker-compose.dev.yml`, `docker-compose.staging.yml`, `docker-compose.prod.yml`
- **Tests Required**: Docker configuration validation & build verification.
- **Verification Evidence**: Docker builds successfully and paths match runtime mount points.

### GAP-14: Database Migrations Reversibility & Schema Drift
- **Component**: Alembic Migrations (`backend/alembic/versions/`)
- **Severity**: Medium (P2)
- **Problem**: Schema changes in Phase 7 required clean migration tracking with downgrade capabilities.
- **Recommended Solution**: Created `0007_phase7_campaign_enhancements.py` adding `business_type`, `company_size`, `min_devices`, `min_score`, `allowed_channels`, `total_email_limit`, `start_date`, and `end_date` with complete `upgrade()` and `downgrade()` routines.
- **Affected Files**: `backend/alembic/versions/0007_phase7_campaign_enhancements.py`
- **Tests Required**: Migration upgrade/downgrade check.
- **Verification Evidence**: `python -m alembic -c backend/alembic.ini current` reports `0007_phase7_campaign_enhancements (head)`.
