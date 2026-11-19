# ActTrident AI Sales Outreach & Automation Agent
## Master 7-Phase Implementation Plan & Repository Audit

**Branch:** `feature/complete-ai-sales-agent`  
**Audit Date:** November 18, 2026  
**Baseline:** Commit `f3fe3f6` (44 passing backend tests, Vite/React 18 Executive Cobalt UI, FastAPI + SQLAlchemy + Celery/Redis architecture)

---

## 1. Repository Audit Summary

### What Already Works (Preserved)
- **Backend Core (`backend/app/`)**: FastAPI REST API with 57 endpoints across Auth, Companies, CRM (16-stage pipeline), Discovery, 7-Factor Qualification, AI Research, Email Generation (5 tones), Human Approval Queue, Campaigns, WhatsApp Cloud API, Inbound Replies (10-class classifier), Analytics, Settings/Audit Logs, and Background Jobs (13 Celery task categories + DLQ + Beat schedule).
- **Frontend (`frontend/src/`)**: React 18 + TypeScript + Vite 6 + Tailwind CSS Executive Cobalt dashboard with 13 functional views (Dashboard, Discovery, Leads, Research, Email Outreach, WhatsApp, Campaigns, Approval Queue, Inbox, CRM Pipeline, Analytics, Integrations, Settings).
- **Security Controls Already Present**: Bcrypt password hashing, JWT access + rotating refresh tokens, public self-registration forced to `sales_rep`, SHA-256 content hashing on email/WhatsApp approvals, Meta webhook HMAC-SHA256 verification, SSRF guard (`is_safe_external_url`), prompt-injection sanitizer, compliance policy engine, suppression list enforcement, demo record flag (`is_demo`).
- **Tests**: 44 unit/integration/security tests passing on in-memory SQLite.

### Critical Gaps Identified (To Be Resolved Across 7 Phases)

| Phase | Existing Gaps & Risks | Planned Resolution |
| :--- | :--- | :--- |
| **Phase 1: Security, Foundation & Reliability** | 1. Hardcoded dev admin credentials pre-filled in `frontend/src/App.tsx`.<br>2. Automatic admin seeding runs in `production` startup.<br>3. No password strength policy on registration/user creation.<br>4. Active JWT access tokens remain valid after logout or account deactivation (no `token_version` invalidation).<br>5. No admin user deactivation / role update endpoints.<br>6. `edit_email_draft` still allows `approval_status="approved"` inside `PUT /emails/drafts/{id}` (violates "editing must never implicitly approve").<br>7. No atomic conditional transition (`approved -> sending`) preventing concurrent double-send race conditions.<br>8. No dedicated immutable `ApprovalRecord` audit table.<br>9. `IntegrationCredential.encrypted_value` is stored in plaintext instead of Fernet-encrypted at rest.<br>10. No **Alembic** database migrations (`alembic.ini` / `alembic/versions/`).<br>11. No structured JSON logging with secret redaction, request correlation IDs (`X-Request-ID`), `/ready` readiness check, or global structured error handlers. | Remove hardcoded UI credentials; forbid auto-admin seeding in production + add CLI provisioner; enforce password complexity; add `User.token_version` + deactivation/role endpoints; remove implicit approval on edit; add atomic dispatch lock + `ApprovalRecord` model; implement Fernet encryption at rest; initialize & verify Alembic migrations (with backup strategy); add structured logging, correlation ID middleware, global error handlers, and `/health` + `/ready` endpoints. |
| **Phase 2: Real Email Integration** | Gmail API OAuth 2.0 flow (`/oauth/gmail/start`, `/oauth/gmail/callback`, token refresh/revocation, connection status UI, reply sync via Gmail API History/Messages, strict state machine `draft -> awaiting_approval -> approved -> queued -> sending -> sent -> delivered/bounced/failed/rejected/cancelled`). | Build `ChannelConnection` encrypted OAuth token store, Gmail OAuth2 flow & adapter, Gmail reply sync job, provider event tracking, and Integrations UI connect/disconnect/status controls. |
| **Phase 3: Real WhatsApp Integration** | Meta template sync endpoint (pull real approval statuses from Meta Graph API instead of assuming local templates are approved), real Meta connection health check, strict template language/parameter ordering validation, webhook delivery/read/failure event state updates. | Build Meta Graph API adapter (`sync_templates`, `health_check`, `send_template`), persist real Meta approval statuses, enforce consent re-check immediately pre-send, verify webhook event idempotency and status transitions. |
| **Phase 4: Real Lead Discovery & Research** | Discovery catalog contains `.example.com` items mixed into standard search; need modular source adapters (OpenStreetMap/Nominatim/Overpass, Search APIs, official website crawler, CSV), explicit provenance (`verified` / `unverified` / `inferred` / `unknown`), strict demo-data isolation so `.example.com` is never presented as a verified company. | Refactor discovery into pluggable source adapters, tag `.example.com` strictly as demo fixtures, persist evidence separate from AI summaries, add field-level verification status and user correction audit trail. |
| **Phase 5: LinkedIn & Multi-Channel Architecture** | No LinkedIn view or common `ChannelAdapter` interface across Email, WhatsApp, and LinkedIn; need documented official LinkedIn API limitations without prohibited scraping/cookie extraction. | Define unified `ChannelAdapter` ABC (`connect`, `connection_status`, `validate_recipient`, `prepare_message`, `send_approved_message`, `receive_event`, `process_webhook`, `sync_conversation`, `disconnect`); implement authorized LinkedIn OAuth/adapter with honest unsupported-feature labels + LinkedIn UI tab + `LINKEDIN_INTEGRATION_GUIDE.md`. |
| **Phase 6: Autonomous Sales Orchestration** | Need campaign pause/resume/stop controls, global emergency "Stop All Outbound Sending" kill switch, business-hours enforcement (IST) in follow-up scheduler, durable transactional outbox pattern, explicit approval requirement for every generated follow-up, and full activity timeline. | Implement `OutboundDispatchOutbox`, campaign lifecycle controls (`active`, `paused`, `stopped`), global kill switch in Settings, IST business-hours guard, and UI controls for human oversight. |
| **Phase 7: Production Readiness, Testing & Deployment** | Need full E2E workflow test (14-step user-to-analytics verification), security test matrix (IDOR, SQLi, XSS, SSRF, prompt injection, webhook spoofing, secret leakage, rate-limit, race condition), DB backup/restore verification, and complete set of 12 documentation deliverables. | Expand pytest suite (unit + integration + E2E + security), verify DB indexes & pagination, verify backup/restore scripts, finalize all 12 documentation guides, and deliver full production-readiness audit. |

---

## 2. Architectural Decision: Background Task Engine

- **Decision:** Keep **Celery 5.4 + Redis 7** with **PostgreSQL persistent task records** (`background_task_records`, `dead_letter_tasks`) and a safe synchronous fallback for local/test environments without Redis.
- **Rationale:** Already integrated into `backend/app/worker/` and `docker-compose.yml`, supports queue isolation (`research`, `outreach`, `high_priority`, `default`), `task_acks_late=True` crash recovery, `Asia/Kolkata` Beat scheduling, and avoids introducing redundant infrastructure.

---

## 3. Risks & Mitigations

1. **Migration Data Loss Risk:** Existing SQLite (`acttrident.db`) or PostgreSQL tables could lose data if altered improperly.  
   *Mitigation:* Always create a timestamped backup before running `alembic upgrade head`, use Alembic batch mode for SQLite compatibility, and test migrations against a backup copy first.
2. **Accidental External Sending Risk:** Live credentials could trigger outbound messages during testing.  
   *Mitigation:* Enforce `EMAIL_PROVIDER=mock` and `WHATSAPP_SEND_MODE=mock` in test/dev; require explicit human approval + atomic dispatch lock; never send external messages without user authorization.
3. **Breaking Existing API Contracts:** Tightening RBAC or schemas could break frontend views or existing tests.  
   *Mitigation:* Update frontend views and regression tests in lockstep within each phase and run the full test suite before completing every phase.
