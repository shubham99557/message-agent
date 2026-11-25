# ActTrident AI Outreach Agent — Security Findings & Remediation Plan

**Date:** 2026-11-14  
**Classification:** Internal Security Review  
**Auditor:** Principal Cybersecurity & Application Security Engineer  

---

## 1. Vulnerability Summary Matrix

| ID | Vulnerability Description | Severity | CWE | Status |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | Privilege escalation via public registration (`role="admin"`) | **Critical** | CWE-269 | Open (Stage 1 target) |
| **SEC-02** | Hardcoded admin credentials in source code & auto-seed on login | **High** | CWE-798 | Open (Stage 1 target) |
| **SEC-03** | Insecure default JWT secret accepted in production | **Critical** | CWE-1188 | Open (Stage 1 target) |
| **SEC-04** | Excessive access token lifetime (7 days) without expiration control | **Medium** | CWE-613 | Open (Stage 1 target) |
| **SEC-05** | Missing refresh token rotation and revocation | **Medium** | CWE-384 | Open (Stage 1 target) |
| **SEC-06** | Approval and administrative endpoints lack role enforcement | **High** | CWE-285 | Open (Stage 1 target) |
| **SEC-07** | Editing approved draft does not invalidate approval state | **Critical** | CWE-863 | Open (Stage 1 target) |
| **SEC-08** | Approved messages lack immutable content hash / version binding | **High** | CWE-353 | Open (Stage 1 target) |
| **SEC-09** | Lack of object-level ownership checks on companies, leads & campaigns | **High** | CWE-639 | Open (Stage 1 target) |
| **SEC-10** | Unauthenticated Meta WhatsApp webhook endpoint (missing HMAC-SHA256) | **Critical** | CWE-354 | Open (Stage 1 target) |
| **SEC-11** | Webhook processing lacks persistence and idempotency protection | **Medium** | CWE-841 | Open (Stage 1 target) |
| **SEC-12** | Overly permissive wildcard CORS (`"*"`) with credentials enabled | **High** | CWE-942 | Open (Stage 1 target) |
| **SEC-13** | Insecure Docker defaults (plain passwords, root user, public DB port) | **Medium** | CWE-250 | Open (Stage 1 target) |
| **SEC-14** | Production prospect records unsegregated from demo/seed data | **Low** | CWE-1188 | Open (Stage 1 target) |
| **SEC-15** | Simulated mock dispatches falsely reported as "sent" and "delivered" | **Medium** | CWE-393 | Open (Stage 1 target) |

---

## 2. Detailed Vulnerability Analyses

### SEC-01: Privilege Escalation via Public Registration
- **Location**: `backend/app/schemas/auth.py`, `backend/app/api/endpoints/auth.py`
- **Impact**: Any unauthenticated visitor calling `POST /api/v1/auth/register` can pass `{"role": "admin"}` and obtain unrestricted administrative access.
- **Remediation**: Hardcode `role="sales_rep"` on self-registration; require administrative authentication for any privileged role assignment.

### SEC-02: Hardcoded Admin Credentials
- **Location**: `backend/app/services/auth_service.py` (`seed_default_admin`)
- **Impact**: Plaintext password `AdminPassword2026!` in source code. Any deployment has known root credentials.
- **Remediation**: Remove hardcoded credentials. Read initial admin email and password securely from environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`). If absent in production, disable auto-seeding.

### SEC-03: Weak / Default JWT Secret
- **Location**: `backend/app/core/config.py`
- **Impact**: Default fallback string `"acttrident-super-secret-production-key-change-in-env-2026"` enables token forgery if not overridden in production.
- **Remediation**: If `ENVIRONMENT == "production"`, enforce that `SECRET_KEY` is at least 32 characters, contains no default substring, or raise an immediate startup error.

### SEC-04 & SEC-05: Token Lifetimes, Rotation & Revocation
- **Location**: `backend/app/core/security.py`, `backend/app/models/user.py`
- **Impact**: Stolen JWT access token is valid for 7 full days without ability to revoke.
- **Remediation**: Reduce access token lifetime to 15-30 minutes. Create `RefreshToken` entity in database storing hashed tokens with expiration and revocation timestamps. Provide `/auth/refresh` and `/auth/logout` endpoints.

### SEC-06: Missing Role Restrictions on Approval Queue
- **Location**: `backend/app/api/endpoints/approvals.py`
- **Impact**: Any user with `sales_rep` role can approve or reject outbound drafts.
- **Remediation**: Guard `/approvals/approve/*`, `/approvals/reject/*`, and `/approvals/bulk` with `require_role(["admin", "manager"])`.

### SEC-07 & SEC-08: Approval Invalidation & Immutable Content Hash
- **Location**: `backend/app/services/approval_service.py`, `backend/app/models/email.py`
- **Impact**: An attacker or rogue user can modify an approved draft's subject or body and dispatch unapproved content without re-triggering approval.
- **Remediation**: Add `content_hash = sha256(subject + body_text)` and `version = Column(Integer, default=1)`. When a draft is edited, automatically reset `approval_status = "draft"` and clear `approved_by_id`. Before sending, verify that `current_hash == approved_content_hash`.

### SEC-09: Object-Level Access Control (IDOR)
- **Location**: `backend/app/api/endpoints/companies.py`, `campaigns.py`
- **Impact**: Any authenticated user can modify or delete any campaign or company.
- **Remediation**: Add `created_by_id` to `Company` and `Campaign`. Check ownership or require `manager`/`admin` role for modifications.

### SEC-10 & SEC-11: Webhook HMAC Verification & Idempotency
- **Location**: `backend/app/api/endpoints/whatsapp.py`
- **Impact**: Unauthenticated POST requests can forge incoming WhatsApp messages or status updates.
- **Remediation**: Validate `X-Hub-Signature-256` using HMAC-SHA256 with `META_APP_SECRET`. Persist incoming events to a `WebhookEvent` table with unique `idempotency_key` before processing.

### SEC-12: Permissive Wildcard CORS
- **Location**: `backend/app/core/config.py`, `backend/app/main.py`
- **Impact**: Wildcard origin `["*"]` combined with `allow_credentials=True` violates browser security standards and allows cross-origin token theft.
- **Remediation**: Reject `["*"]` when credentials are enabled. Configure explicit allowed origins (e.g., `["http://localhost:5173", "http://localhost:3000"]`).

### SEC-13: Insecure Docker Defaults
- **Location**: `docker-compose.yml`, `docker/Dockerfile.backend`
- **Impact**: Hardcoded postgres password, exposed port 5432 to host, and backend container running as root user.
- **Remediation**: Use non-root user in Dockerfile, enforce environment variable injection for DB passwords, and restrict internal service exposure.

### SEC-14: Demo Data Separation
- **Location**: `backend/app/models/company.py`, `backend/seed_data.py`
- **Impact**: Fictional seed records risk being included in live sales campaigns.
- **Remediation**: Add `is_demo: bool = True` to all seed companies and leads. Filter out demo data in live production campaign selectors.

### SEC-15: Simulated Message Reporting
- **Location**: `backend/app/services/email_sender_service.py`, `whatsapp_service.py`
- **Impact**: Mock runs generate false positive delivery statistics and pollute CRM timeline.
- **Remediation**: Explicitly mark mock dispatches as `status="simulated"` and do not emit fake `delivered` events without provider receipt.
