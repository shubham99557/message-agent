# ActTrident — Final Comprehensive Repository & Architecture Audit

**Date:** November 22, 2026  
**Auditor:** Principal Software Architect & Release Engineering Team  
**Git Working Branch:** `feature/production-hardening-final`  
**Starting Commit:** `ea8bd5a`  
**Remote Origin:** `https://github.com/shubham99557/message-agent.git`  
**Overall Codebase Status:** Production Hardening Active  

---

## 1. Executive Summary & Repository Status

ActTrident is an AI-powered B2B sales research and outreach desktop application designed for local-first operation on Windows PCs with local Ollama inference (`llama3.2:latest`) accelerated on an NVIDIA GTX 1650 Max-Q GPU.

A complete review of all 24 modified/created modules and historical code was conducted. While earlier phases successfully established the core architecture, several unsafe defaults, non-durable in-memory states, and missing policy enforcements were identified that require systematic hardening before release.

---

## 2. Component-by-Component Architectural Audit

### 2.1 Backend Architecture & API Routing
- **Framework:** FastAPI with async lifespan management and structured correlation ID middleware (`X-Request-ID`).
- **Mount Point:** All endpoints mounted under `/api/v1` in `backend/app/api/api_v1.py`.
- **Finding:** Clean route modularization across 18 routers (`auth`, `agent`, `ai`, `companies`, `crm`, `discovery`, `qualification`, `research`, `emails`, `approvals`, `campaigns`, `whatsapp`, `linkedin`, `replies`, `analytics`, `settings`, `jobs`, `integrations`, `automation`).
- **Correction Required:** Remove or disable any remaining bulk approval logic in `approvals.py` regardless of `LIVE_SEND_ENABLED`.

### 2.2 SQLAlchemy Models & Database Layer
- **ORM:** SQLAlchemy declarative models under `backend/app/models/`.
- **Finding:**
  - `Company`: Successfully updated with `laptop_fleet_status = Column(String(50), default="UNKNOWN")`.
  - `EmailDraft`: Added `missing_recipient` to `EMAIL_STATES`; `recipient_email` is now nullable.
  - `OutboundDispatchOutbox`: Transactional outbox model exists with `idempotency_key` and `attempts`.
- **Deficiency Identified:** The persistent local scheduler relies on an in-memory dictionary for `last_run` and `task_stats`. If the FastAPI process restarts, schedule history is lost.
- **Correction:** Create `SchedulerJobRecord` and `SchedulerExecutionHistory` models in `backend/app/models/orchestration.py` to persist job states directly into SQLite.

### 2.3 Database Configuration & Windows Desktop Path Resolution
- **Files:** `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/app/core/storage.py`.
- **Finding:** `storage.py` defines `resolve_local_database_path()` pointing to `%LOCALAPPDATA%\ActTrident\data\acttrident.db`. However, `database.py` instantiated `create_engine` directly from `settings.DATABASE_URL` (`sqlite:///./acttrident.db`), meaning local runs defaulted to the project root directory instead of the persistent Windows AppData location.
- **Correction:** Wire `database.py` to resolve the persistent database path from `resolve_local_database_path()` unless an explicit override (e.g. `:memory:` in tests) is provided.

### 2.4 Authentication, RBAC, and First-Run Setup
- **Files:** `backend/app/api/endpoints/auth.py`, `backend/app/services/auth_service.py`.
- **Finding:** JWT access tokens (30m expiry) and refresh tokens (14d expiry) implemented. Default administrator credentials (`AdminSecretPass2026!`) are seeded if no admin exists.
- **Correction:** Provide a secure first-run administrator configuration wizard in the Windows desktop launcher and require a password change on first login.

### 2.5 Local AI Brain (Ollama) & Structured Output
- **Files:** `backend/app/ai/structured_output.py`, `backend/app/ai/local_ai_gateway.py`, `backend/app/ai/ollama_provider.py`.
- **Findings & Unsafe Defaults Identified:**
  - `ResearchDossierOutput`: `relevance_score` defaulted to `80.0` and `confidence_rating` to `"medium"`. Must default to `0.0` and `"low"` or unknown.
  - `ReplyClassificationAIOutput`: `classification` defaulted to `"interested"` and `confidence` to `0.9`. Must default to `"unknown"` and `0.0`.
  - `DeterministicFallbackProvider`: Fallback methods previously returned positive responses when Ollama was offline. This was partially addressed, but needs complete zero-score / `ai_unavailable` enforcement across all methods.
- **Ollama Reliability:** Model verification and health check diagnostics must clearly distinguish between Ollama offline, model missing, inference timeout, and successful generation.

### 2.6 Lead Discovery & Evidence Model
- **Files:** `backend/app/services/discovery_service.py`, `backend/app/integrations/discovery_adapters.py`.
- **Finding:** OpenStreetMap queries discover municipal entities. Demo fixtures are quarantined when `include_demo=False`.
- **Deficiency:** A directory listing or OpenStreetMap entry was previously capable of setting `laptop_count_verified = 6` with fake evidence. This was removed in `autonomous_agent_service.py`, but must be enforced across all discovery adapters: OSM must only provide geographic and business identity data; laptop fleet must remain `UNKNOWN` until external evidence is verified.

### 2.7 Seven-Factor Lead Qualification
- **File:** `backend/app/services/qualification_service.py`.
- **Deficiency Identified:** Factors previously awarded consolation points (2.0 to 5.0 points) even when a factor failed or when evidence was missing.
- **Correction:** Strict zero-point rule for unknown or missing evidence. Factor 4 (browser workflows) and Factor 5 (data handling) must check for actual evidence in tech stacks or business descriptions rather than inferring them from `is_tech`.

### 2.8 Real Ollama Content Generation & Product Claims
- **Files:** `backend/app/services/email_generator_service.py`, `backend/app/core/product_claims.py`.
- **Finding:** `build_email_content` previously used template strings.
- **Correction:** Connect real Ollama generation via `local_ai_gateway.generate_email_draft()` when Ollama is available, validating every draft against `validate_message_against_claims()`. The 90-day evaluation offer must be guarded by explicit configuration (`settings.ALLOW_90_DAY_EVALUATION_OFFER`).

### 2.9 Mandatory Individual Human Approval
- **Files:** `backend/app/services/approval_service.py`, `backend/app/api/endpoints/approvals.py`.
- **Finding:** `bulk_handle_approvals` allowed bulk approval when `LIVE_SEND_ENABLED=False`.
- **Correction:** Bulk approval for outbound messaging must be completely removed/disabled regardless of `LIVE_SEND_ENABLED`. Canonical SHA-256 hash must bind: `[draft.id, company_id, recipient_email, channel, campaign_id, subject, body_text]`. Any modification immediately resets approval.

### 2.10 Gmail & WhatsApp Integrations
- **Gmail:** Uses official OAuth 2.0 flow with refresh token handling and local mock/test/live separation.
- **WhatsApp:** `seed_default_meta_templates` seeded templates with status `"APPROVED"`. Must be seeded as `"PENDING_META_VERIFICATION"` until verified via Meta API webhook/response.

### 2.11 Persistent Windows Automation Scheduler
- **File:** `backend/app/services/local_scheduler.py`.
- **Deficiency:** Relied on in-memory state.
- **Correction:** Persist job schedules, last run timestamps, next due timestamps, and execution history in SQLite tables `scheduler_job_records` and `scheduler_execution_history`.

---

## 3. Corrective Action Plan (Phases 1–20)

| Phase | Target Area | Planned Remediation |
| :--- | :--- | :--- |
| **Phase 1** | AI Truthfulness | Remove all positive defaults in `structured_output.py`. Explicit `unknown` / `ai_unavailable` states. |
| **Phase 2** | Discovery & Evidence | Enforce `VERIFIED`, `CLAIMED`, `UNKNOWN` strictly. No `.example.com` synthetic companies in live results. |
| **Phase 3** | 7-Factor Qualification | 0 points for unknown info. Ground browser workflows & data handling in documented evidence. |
| **Phase 4** | Real Ollama Copywriting | Connect live Ollama generation to emails, WhatsApp, and LinkedIn drafts. Claims validation. |
| **Phase 5** | Product Claims | Central authoritative registry. Guard commercial evaluation offers by configuration. |
| **Phase 6** | Mandatory Individual Approval | Completely disable outbound bulk approval. Canonical SHA-256 hash binding 7 fields. |
| **Phase 7** | Gmail Integration | Official OAuth 2.0, clear mock/test/live separation, bounce and reply association. |
| **Phase 8** | WhatsApp Integration | Set seeded templates to `PENDING_META_VERIFICATION`. Support manual click-to-chat fallback. |
| **Phase 9** | LinkedIn Workflow | Compliant manual handoff, character limit validation, copy-to-clipboard, sent confirmation. |
| **Phase 10** | Transactional Outbox | Atomic claim (`pending` -> `processing`), immediate pre-dispatch kill switch & hash verification. |
| **Phase 11** | Reply Classification | 8 canonical classes (`INTERESTED`, `NOT_INTERESTED`, `NEEDS_INFORMATION`, etc.), zero default confidence on unknown. |
| **Phase 12** | Follow-Up Cadence | Enforce IST business hours, max follow-up limits, mandatory new approval per follow-up. |
| **Phase 13** | Database Persistence | Ensure `database.py` uses `%LOCALAPPDATA%\ActTrident\data\acttrident.db`. Test restart survival. |
| **Phase 14** | Durable Scheduler | Store scheduler state in SQLite. Missed-run recovery after PC reboot. |
| **Phase 15** | Security Hardening | Sanitize untrusted web text, prevent prompt injection, secure headers, bind 127.0.0.1. |
| **Phase 16** | Automation Center UI | Accurate telemetry, real-time IST clock, kill switch toggle, zero fake data. |
| **Phase 17** | Testing & Proof | Full test suite execution (`pytest -v`), Vite build, E2E workflow proof. |
| **Phase 18** | Windows Release | Built frontend serving, unified Windows launcher script, first-run wizard. |
| **Phase 19** | Documentation | Update all outdated guides in `docs/` and root `README.md`. |
| **Phase 20** | Final Release Audit | Objective release assessment and classification (`PRODUCTION CANDIDATE`). |
