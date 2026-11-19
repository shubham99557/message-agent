# ActTrident Security Audit & Threat Model

**Platform**: ActTrident AI Outreach & Sales Automation  
**Audit Standard**: OWASP Top 10 API Security Risks (2023), NIST SP 800-63B  
**Status**: PASSED / HARDENED  
**Date**: November 2026

---

## 1. Executive Summary

ActTrident handles high-value corporate outreach across multiple digital channels (Email, WhatsApp, LinkedIn), enterprise lead discovery data, and system-level credentials. This security audit evaluated the application's attack surface, defensive controls, cryptographic integrity, and compliance policies.

All identified vulnerabilities—including SSRF in discovery scraping, missing JWT token version checks, credential exposure risks, unauthenticated webhooks, and unauthorized cross-account mutations—have been remediated and verified with regression tests.

---

## 2. Authentication & Session Management

### 2.1 Password Hashing & Policy
- **Algorithm**: `bcrypt` with work factor 12 (via Passlib).
- **Policy Enforcement**: Minimum 8 characters, at least 1 uppercase letter, 1 lowercase letter, and 1 numeric digit. Enforced via Pydantic validator on both public registration and administrative provisioning.
- **Timing Attack Resistance**: Constant-time comparison on password verification (`bcrypt.checkpw`).

### 2.2 JWT Architecture & Token Version (`tv`) Enforcement
- **Algorithm**: `HS256` signed by `SECRET_KEY` (minimum 32-character entropy required in production).
- **Access Token TTL**: 60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Refresh Token TTL**: 7 days (`REFRESH_TOKEN_EXPIRE_DAYS`).
- **Instant Revocation via `tv` Claim**:
  - Every access token embeds a `tv` (token version) integer claim.
  - The authentication dependency (`app.api.deps.get_current_user`) checks the token's `tv` against the live PostgreSQL user record on **every single request**.
  - Any administrative password reset, role update, or session revocation increments `User.token_version`, immediately invalidating all existing JWTs across all active client devices without waiting for expiration.
  - Tokens missing the `tv` claim are rejected with `HTTP 401 Unauthorized`.

### 2.3 Refresh Token Rotation & Replay Detection
- Refresh tokens are cryptographically random strings (32 bytes / 64 hex characters).
- Stored as SHA-256 hashes in the `refresh_tokens` database table; raw tokens are never persisted in plaintext.
- **Rotation**: On every refresh request, the existing token is marked `revoked_at=utcnow()` and replaced with a new token.
- **Replay Protection**: If a revoked refresh token is presented, the system detects a potential replay attack, logs a security warning, and revokes all active refresh tokens for that user account.

---

## 3. Role-Based Access Control (RBAC) & Authorization

ActTrident implements four discrete roles with strict separation of duties:

| Role | Intended Persona | Permitted Operations | Restricted Operations |
|---|---|---|---|
| **`admin`** | Super Administrator / DevOps | Full system control: user provisioning, role promotion/demotion, API integration credentials, global kill switch, suppression list, audit logs, all operational features. | Cannot demote or deactivate their own active administrator account. |
| **`manager`** | Sales Director / Campaign Lead | Campaign creation/scheduling/dispatch, approval queue review/approve/reject/reschedule, CRM pipeline management, trigger background tasks, toggle global kill switch. | Cannot provision new users, cannot edit integration API keys/secrets. |
| **`sales_rep`** | Sales Operator / BDR | Lead discovery, company creation, campaign draft creation, editing/verifying records they created, moving CRM leads through stages. | Cannot approve messages for delivery, cannot execute bulk sends, cannot modify records created by other reps, cannot access admin settings. |
| **`analyst`** | Executive / Market Researcher | Complete read-only access: view analytics dashboards, city breakdowns, campaign metrics, company evidence, approval queue, CRM leads, and export CRM CSV reports. | **Zero mutation privileges**: Cannot create, update, delete, or dispatch any campaign, company, draft, or CRM record (all return `HTTP 403 Forbidden`). |

### Multi-Tenant Ownership Isolation
- Company records and email drafts enforce strict creator ownership for `sales_rep` accounts (`created_by_id == current_user.id`).
- Unauthorized modification attempts return `HTTP 403 Forbidden: You do not own this record or require manager privileges`.

---

## 4. Network & Input Security: SSRF Prevention

Lead discovery and company website enrichment allow users and automated scrapers to query company websites. To prevent Server-Side Request Forgery (SSRF) against internal VPC services, container networks, and cloud metadata APIs:

- **Validation Function**: `app.core.security.is_safe_external_url(url)`.
- **IP Blocklist**:
  - Loopback (`127.0.0.0/8`, `localhost`, `::1`)
  - Cloud Metadata endpoints (`169.254.169.254`, `metadata.google.internal`)
  - RFC 1918 Private Ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
  - Link-local and carrier-grade NAT (`100.64.0.0/10`)
- **Protocol Restriction**: Only `http://` and `https://` schemes are permitted; `file://`, `gopher://`, `ftp://` are blocked.
- **DNS Rebinding Protection**: Resolved IP addresses are validated prior to initiating outbound HTTP requests.

---

## 5. Webhook Security & HMAC Verification

### Meta WhatsApp Cloud Webhooks
- **Handshake Verification**: `GET /api/v1/whatsapp/webhook` verifies `hub.mode == 'subscribe'` and compares `hub.verify_token` against `settings.META_WA_VERIFY_TOKEN` using constant-time comparison (`secrets.compare_digest`).
- **Payload Signature Validation**: `POST /api/v1/whatsapp/webhook` inspects the `X-Hub-Signature-256` header, computing the HMAC-SHA256 signature using `settings.META_WA_APP_SECRET`. Payloads with invalid or missing signatures are rejected with `HTTP 403 Forbidden`.

---

## 6. Cryptographic Secret Management

- **OAuth Tokens & Client Secrets**: Stored encrypted in the database using AES-128-CBC / HMAC-SHA256 via the Python `cryptography.fernet.Fernet` suite.
- **Key Derivation**: `ENCRYPTION_KEY` is injected strictly via environment variables; never hardcoded in source control.
- **Zero In-Memory Leakage**: Tokens and secrets are masked in API responses and frontend settings views.

---

## 7. Tamper-Evident Audit Logging

Every security-sensitive and operational action is recorded to the immutable `audit_logs` table:
- User ID (or system daemon marker)
- Action type (`login`, `create_campaign`, `approve_email_draft`, `toggle_kill_switch`, etc.)
- Entity type & ID
- Timestamp (UTC)
- Metadata payload (excluding passwords and tokens)
- Audit logs cannot be updated or deleted via standard API endpoints.

---

## 8. Emergency Outbound Kill Switch

ActTrident incorporates an emergency kill switch mechanism (`SystemSetting: global_outbound_kill_switch`):
- When active, all outbound communication across Email, WhatsApp, LinkedIn, transactional outbox, and Celery background workers is immediately blocked.
- Any manual or scheduled send request returns `HTTP 423 Locked`.
- Can be triggered instantly by `admin` or `manager` roles from the Settings UI or API.
