# ActTrident AI Outreach Agent — Implementation Roadmap

**Branch:** `feature/autonomous-automation`  
**Execution Strategy:** Phased rollout with automated testing after every stage  

---

## Stage Breakdown & Milestones

### Stage 0: Comprehensive Codebase Audit & Planning (Complete)
- [x] Audit all backend & frontend modules.
- [x] Create `CODEBASE_AUDIT.md`.
- [x] Create `SECURITY_FINDINGS.md`.
- [x] Create `AUTOMATION_ARCHITECTURE.md`.
- [x] Create `IMPLEMENTATION_ROADMAP.md`.

### Stage 1: Critical Security Fixes
- [ ] Fix public registration role escalation (restrict to `sales_rep`).
- [ ] Remove hardcoded default admin credentials from code; read from environment.
- [ ] Reject weak/default JWT secrets in production; add strict validation.
- [ ] Implement short-lived access tokens (15-30m) and refresh token rotation with revocation (`RefreshToken` model).
- [ ] Enforce role checks (`admin`, `manager`) on approval and administrative endpoints.
- [ ] Invalidate approval when an approved message draft is edited.
- [ ] Add immutable content hashing (`sha256`) and version tracking to message drafts.
- [ ] Add ownership validation (`created_by_id`) and IDOR protection on companies, campaigns, leads.
- [ ] Implement Meta WhatsApp webhook HMAC-SHA256 signature verification (`X-Hub-Signature-256`).
- [ ] Implement persistent webhook event storage with idempotency deduplication (`WebhookEvent` model).
- [ ] Replace wildcard production CORS with configurable explicit origins.
- [ ] Secure Docker configuration (non-root user, internal database networking).
- [ ] Separate demo data (`is_demo` flag) from live prospect records.
- [ ] Prohibit reporting simulated dispatches as real "sent" or "delivered".
- [ ] Write security regression test suite and verify passing.

### Stage 2: Background Job Engine (Celery + Redis)
- [ ] Add Redis and Celery dependencies to `requirements.txt` and `docker-compose.yml`.
- [ ] Create Celery app configuration, task routing, and rate limiters.
- [ ] Implement task models in PostgreSQL for persistent task history and DLQ.
- [ ] Implement all 13 task categories with exponential backoff and idempotency keys.
- [ ] Expose job health, queue latency, and task status API endpoints and frontend widget.

### Stage 3: Real Company Discovery Engine
- [ ] Build pluggable search/directory adapters (Google Custom Search, Bing, MCA public registry).
- [ ] Implement structured scraping of verified corporate directories.
- [ ] Retain source attribution URL, retrieval timestamp, and confidence for every field.
- [ ] Enforce laptop fleet evidence separation (explicit `Unknown` when absent).

### Stage 4: Enhanced Lead Qualification Engine
- [ ] Extend 7-factor qualification with detailed evidence citations and timestamps.
- [ ] Add automated re-verification cron for stale records (> 60 days old).

### Stage 5: Orchestrated AI Research Agent
- [ ] Multi-step agent workflow: website crawling -> tech stack extraction -> ActTrident use case matching.
- [ ] Strict truthfulness guardrails against hallucinated breaches or false claims.

### Stage 6: Production Email Automation (Gmail API OAuth2 + SMTP)
- [ ] Implement real Google OAuth 2.0 flow with encrypted token storage.
- [ ] Implement thread tracking, bounce parsing, and unsubscribes.
- [ ] Enforce strict message lifecycle (`draft -> approved -> queued -> sending -> sent`).

### Stage 7: Production Meta WhatsApp Automation
- [ ] Graph API v19.0/v20.0 integration with Meta template status synchronization.
- [ ] Enforce verified consent records before queuing any automated message.
- [ ] Instant opt-out processing and global suppression synchronization.

### Stage 8: Autonomous Follow-Up Engine
- [ ] Timezone-aware business day scheduler (Asia/Kolkata).
- [ ] Configurable multi-step sequences with automated halt on reply, bounce, or opt-out.
- [ ] Mandatory human review gate for follow-up dispatches.

### Stage 9: Unified Inbox & CRM
- [ ] Ingest email and WhatsApp threads into single conversation timeline.
- [ ] AI sentiment classification (10 categories) and suggested responses.
- [ ] Strict human sign-off on pricing, negotiation, and contract discussions.

### Stage 10: Scheduled Daily Automation & Reporting
- [ ] Celery Beat periodic tasks for nightly discovery, stale re-check, and digest reporting.
- [ ] Real-time queue health and operational metrics dashboard.

### Stage 11: Human Approval & Policy Engine
- [ ] Role-restricted approval workflows with audit logging.
- [ ] Configurable approval policies (pre-approval thresholds for vetted templates).

### Stage 12: Production Hardening, E2E Verification & Documentation
- [ ] Comprehensive test suite covering privilege escalation, concurrency, and failure recovery.
- [ ] Final operator manual and deployment documentation.
