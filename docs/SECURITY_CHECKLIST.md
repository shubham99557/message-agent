# ActTrident Security Checklist & Verification Matrix

**Standard**: OWASP Top 10 API Security Risks (2023), NIST SP 800-63B  
**Platform**: ActTrident AI Outreach & Sales Automation  
**Audit Status**: 100% VERIFIED & HARDENED

---

## 1. Authentication & Session Security

- [x] **Bcrypt Password Hashing**: Passwords hashed using bcrypt with work factor 12. Plaintext passwords are never logged or stored.
- [x] **Password Complexity Policy**: Minimum 8 characters, requiring at least one uppercase letter, one lowercase letter, and one number. Validated via Pydantic model (`app.schemas.auth._validate_strong_password`).
- [x] **JWT Access Token TTL**: Short-lived (60 minutes).
- [x] **Mandatory Token Version (`tv`) Claim**: Every access token contains a `tv` claim checked against the live PostgreSQL user record on every authenticated request.
- [x] **Instant Session Revocation**: Deactivating a user, updating their role, or logging out increments `User.token_version`, instantly invalidating active JWTs across all client sessions without waiting for expiration.
- [x] **Rotating Refresh Tokens**: Refresh tokens stored as SHA-256 hashes in `refresh_tokens` table. Automatically rotated upon use; reuse of a revoked token triggers an immediate session purge.

---

## 2. Authorization & Role-Based Access Control (RBAC)

- [x] **Separation of Duties (Campaign Approvals)**: Only `admin` and `manager` roles can approve, reject, schedule, or bulk-manage outreach drafts. Sales representatives (`sales_rep`) and analysts (`analyst`) attempting to approve drafts receive `HTTP 403 Forbidden`.
- [x] **Read-Only Analyst Role**: The `analyst` role has full read access to analytics, CRM pipelines, campaigns, companies, and jobs health, but is strictly blocked (`HTTP 403 Forbidden`) from all creation, modification, deletion, and dispatch actions.
- [x] **Object-Level Ownership**: `sales_rep` users can only view and modify companies and email drafts they created (`_check_draft_ownership`). Cross-representative edits are blocked with `HTTP 403 Forbidden`.
- [x] **Super Admin Privilege Protection**: Administrators cannot demote or deactivate their own active account (`HTTP 400 Bad Request`).
- [x] **Public Registration Hardening**: Public self-registration (`POST /api/v1/auth/register`) strictly forces `role="sales_rep"`. Privilege escalation via registration payload is blocked.

---

## 3. Network, Input & Data Protection

- [x] **Server-Side Request Forgery (SSRF) Protection**: All external URLs (website scraping, company domains) are validated via `is_safe_external_url()`. Loopback addresses (`127.0.0.1`, `localhost`), link-local/cloud metadata (`169.254.169.254`), and private RFC 1918 networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) are strictly rejected.
- [x] **SQL Injection Defense**: 100% of database interactions utilize SQLAlchemy ORM parameterized queries or bound statements. Zero raw string concatenation in SQL queries.
- [x] **XSS Sanitization**: User-supplied text and website descriptions are sanitized via `sanitize_untrusted_text()`. HTML payloads are strictly escaped before template rendering.
- [x] **File Upload Validation**: CSV imports enforce `.csv` extension validation, maximum file size limits (10 MB), and UTF-8 encoding decoding with safe replacement.

---

## 4. Webhooks & Outbound Communication Safety

- [x] **Meta WhatsApp Webhook HMAC-SHA256**: Inbound WhatsApp webhooks validate the `X-Hub-Signature-256` header against `META_WA_APP_SECRET` using constant-time comparison (`secrets.compare_digest`). Unsigned or forged payloads are rejected (`HTTP 403 Forbidden`).
- [x] **WhatsApp Verification Token**: Handshake requires exact match with `META_WA_VERIFY_TOKEN`. Hardcoded fallback secrets have been completely removed from frontend code.
- [x] **Cryptographic Content Hashing**: Approving an email draft computes an immutable SHA-256 hash of `subject + body_text` stored in `approved_content_hash`. Modifying an approved draft immediately clears the approval, increments the draft version, and requires re-approval.
- [x] **Emergency Global Outbound Kill Switch**: Setting `global_outbound_kill_switch` halts all outbound sends across Email, WhatsApp, LinkedIn, transactional outbox, and Celery beat tasks immediately (`HTTP 423 Locked`).
- [x] **Dual Outbound Rate Limiting**: Enforces a sliding-window burst rate limit (maximum 10 messages per minute) and daily campaign limits (50 emails/day, 20 WhatsApp/day) across synchronous and asynchronous dispatch paths.
- [x] **Automatic Opt-Out & Suppression**: Inbound WhatsApp `STOP` replies, Gmail bounce notifications, and manual opt-out requests immediately register in `suppression_list`. Outbound dispatch pre-checks suppression registry before any external call.

---

## 5. Secret Hygiene & Cryptography

- [x] **Zero Hardcoded Secrets**: Zero API keys, passwords, or OAuth client secrets committed in Git. All secrets managed via environment variables.
- [x] **Symmetric Token Encryption**: Third-party OAuth tokens and secrets stored in PostgreSQL are encrypted at rest using AES-128-CBC / HMAC-SHA256 via `cryptography.fernet.Fernet` with `ENCRYPTION_KEY`.
- [x] **Log Redaction**: Passwords, tokens, authorization headers, and private customer details are automatically redacted from application logs via `redact_sensitive_text()`.
- [x] **Tamper-Evident Audit Logging**: All security actions, approvals, user creations, role changes, and kill switch toggles are logged to the immutable `audit_logs` table.
