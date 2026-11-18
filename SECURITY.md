# ActTrident AI Sales Outreach & Automation Agent — Security Architecture & Controls

## 1. Authentication & Session Security
- **Password Hashing**: `bcrypt` with per-password random salts; password policy enforces ≥8 chars with uppercase, lowercase, and digit.
- **Short-Lived JWT Access Tokens**: Default 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES=30`), signed with `SECRET_KEY` (minimum 32 characters enforced at production startup).
- **Refresh Token Rotation**: 14-day refresh tokens stored as SHA-256 hashes in `refresh_tokens`; rotation invalidates prior tokens.
- **Immediate Session Revocation**: `User.token_version` is verified against the database on every request. Logout (`POST /api/v1/auth/logout`), role changes (`PATCH /api/v1/auth/users/{id}/role`), and account deactivation (`PATCH /api/v1/auth/users/{id}/status`) increment `token_version` and revoke all refresh tokens immediately.
- **No Hardcoded Production Admin**: Automatic admin seeding is disabled when `ENVIRONMENT=production`. Production admins are provisioned via `backend/scripts/provision_admin.py`.

## 2. Role-Based Access Control (RBAC) & Ownership
- Public registration (`POST /api/v1/auth/register`) strictly assigns `sales_rep` only.
- `admin` / `manager` required for: approving/rejecting/dispatching Email, WhatsApp, and LinkedIn drafts; Gmail & LinkedIn OAuth initiation; campaign pause/resume/stop; Global Kill Switch toggle; outbox & background job triggers.
- `admin` required for: user role/status changes, integration secret writes, OAuth disconnect, audit log reads.
- Campaign ownership checks prevent IDOR edits or recipient injection by non-owning `sales_rep` users.

## 3. Secrets & Encryption at Rest
- All stored integration secrets (`IntegrationCredential.encrypted_value`) and OAuth access/refresh tokens (`ChannelConnection.encrypted_access_token` / `encrypted_refresh_token`) are **Fernet-encrypted at rest** using `CREDENTIAL_ENCRYPTION_KEY`.
- API responses expose only `has_secret` and masked values — never plaintext tokens or keys.
- Structured JSON logs (`logging_config.py`) redact Bearer JWTs, API keys (`sk-...`, `AIza...`, `EAAB...`), and secret assignments automatically.

## 4. Approval Integrity & Anti-Double-Send Guards
- Every approved message stores a canonical SHA-256 `content_hash` and an immutable `ApprovalRecord`.
- Editing any approved draft automatically resets `approval_status` to `draft`, clears approver metadata, and records `invalidated_by_edit`.
- Outbound dispatch uses atomic SQL conditional state claims (`approved → sending` / `pending → processing`) plus deterministic `idempotency_key` columns to eliminate concurrent double-send races.

## 5. External Input, Webhook & Scraping Defenses
- **SSRF Protection**: `is_safe_external_url()` blocks non-HTTP(S) schemes, `localhost`, loopback, RFC-1918 private networks, and cloud metadata IPs (`169.254.169.254`).
- **XSS & Prompt Injection Defense**: `sanitize_untrusted_text()` strips `<script>`, `<style>`, `<iframe>`, `<object>`, `<embed>`, `javascript:` URIs, and prompt-override patterns from all external web content.
- **Meta Webhook Verification**: `POST /api/v1/whatsapp/webhook` verifies `X-Hub-Signature-256` HMAC-SHA256 using `META_APP_SECRET` in constant time (`hmac.compare_digest`) and deduplicates payloads in `webhook_events`.
- **LinkedIn Anti-Ban Policy**: Uses Official OAuth 2.0 & approved Partner APIs only — zero password collection, zero cookie (`li_at`) extraction, zero scraping.

## 6. Production Startup Fail-Fast Guards
When `ENVIRONMENT=production`, startup (`config.py`) aborts immediately if:
1. `SECRET_KEY` is weak/default or `< 32` characters.
2. `BACKEND_CORS_ORIGINS` contains `*`.
3. `CREDENTIAL_ENCRYPTION_KEY` is missing or `< 16` characters.
4. `DATABASE_URL` uses SQLite instead of PostgreSQL.
