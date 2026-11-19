# ActTrident Enterprise Security Audit & Hardening Specification

**Date:** November 19, 2026  
**Auditor Roles:** Senior Application Security Engineer & Principal Backend Architect  
**Classification:** Confidential — Internal Security Baseline  

---

## 1. Executive Summary

A comprehensive application security audit was performed across ActTrident's backend API, background workers, integration adapters, and frontend client. All 20 designated security dimensions were evaluated and hardened to enterprise SaaS standards.

---

## 2. Comprehensive Security Review Across 20 Dimensions

### 1. Authentication
- Implemented RFC 7519 JWT-based authentication.
- All tokens include `sub` (email), `role`, `user_id`, `tv` (token version), and UTC `exp`.
- Tokens without valid signatures or missing claims are immediately rejected with `401 Unauthorized`.

### 2. JWT Validation & Revocation
- Token version (`tv`) claim is bound to the user's database `token_version`.
- Any password change or session revocation increments `token_version`, instantly invalidating all outstanding access and refresh tokens.

### 3. Refresh Token Rotation & Hashing
- Refresh tokens are cryptographically random 48-byte URL-safe strings generated via `secrets.token_urlsafe(48)`.
- Persisted in the database strictly as SHA-256 hashes (`hash_token()`). Plaintext tokens are never stored.
- One-time use: Each refresh operation revokes the consumed token and issues a fresh pair.

### 4. Password Hashing
- Uses bcrypt with auto-generated salts.
- Known default development passwords (`AdminPassword2026!`, `SalesPassword2026!`, etc.) are actively barred in production by `validate_production_security()`.

### 5. Role-Based Access Control (RBAC)
- Strict hierarchy: `admin` > `manager` > `sales_rep` > `analyst`.
- Sensitive operations (approving drafts, dispatching live campaigns, managing integrations, toggling kill switch) require `admin` or `manager` roles.
- `sales_rep` attempts to approve drafts receive `403 Forbidden`.

### 6. Object-Level Authorization
- Multi-tenant and user ownership checks ensure sales representatives can only view and edit leads or drafts assigned to them.
- Direct object reference vulnerabilities (IDOR) are blocked via ownership validation in service queries.

### 7. Cross-Origin Resource Sharing (CORS)
- Wildcard CORS (`*`) is strictly forbidden in production and raises a critical startup exception in `validate_production_security()`.
- Allowed origins are explicitly parsed from environment configurations (`http://localhost:5173`, `https://app.acttrident.ai`).

### 8. Cross-Site Request Forgery (CSRF)
- OAuth 2.0 flows (Google Workspace, LinkedIn) implement cryptographically random `state` parameters stored in Redis or memory with short expiration and validated on callback.

### 9. Cross-Site Scripting (XSS)
- All untrusted text from external websites and CSV files is sanitized via `sanitize_untrusted_text()`.
- Strips `<script>`, `<style>`, `<iframe>`, `<object>`, `<embed>` blocks and filtered `javascript:` URIs.

### 10. SQL Injection Prevention
- 100% of database interactions utilize SQLAlchemy 2.0 ORM or parameterized Core statements.
- Zero string interpolation or concatenation in SQL execution paths.

### 11. Server-Side Request Forgery (SSRF) Hardening
- Dual-stack DNS resolution (`socket.getaddrinfo`) blocks both IPv4 and IPv6 private, loopback, link-local, and reserved ranges.
- Cloud metadata endpoints (`169.254.169.254`, `fd00:ec2::254`, `metadata.google.internal`) are explicitly blocked.
- Dedicated `safe_fetch_untrusted_url()` inspects every 3xx redirect hop individually; relative URLs are resolved and re-validated before fetching.
- High-risk internal ports (22, 25, 5432, 6379, 8000, 27017) are blocked.

### 12. Prompt Injection Defense
- Incoming website content passes through regex filtering for instruction-override patterns (`ignore previous instructions`, `system prompt`, `you are now`, `developer mode`).
- Untrusted content is enclosed in structural delimiter tags during AI prompt assembly.

### 13. File Upload Safety
- CSV imports validate `.csv` extensions, enforce size limits, and parse row-by-row with DictReader.
- Binary executable formats or unexpected MIME types are rejected.

### 14. Webhook Signature Verification
- Meta WhatsApp Cloud API webhooks verify incoming payloads using HMAC-SHA256 against `META_APP_SECRET`.
- Constant-time comparison (`hmac.compare_digest`) prevents timing attacks.

### 15. Secret Storage & Encryption at Rest
- Sensitive third-party credentials (Google refresh tokens, WhatsApp access tokens, LinkedIn tokens) are encrypted at rest using AES-128-CBC / HMAC-SHA256 via Fernet cryptography.
- Plaintext secrets are never stored in the database.

### 16. OAuth Token Handling
- OAuth authorization codes are exchanged via secure server-to-server TLS connections.
- Expired tokens refresh automatically; revoked tokens transition channel connection status to `disconnected`.

### 17. Session Revocation
- Global logout and password rotation endpoints invalidate active JWTs by incrementing the user's `token_version`.

### 18. Rate Limiting & Throttling
- Sliding window rate limiting implemented across both Redis and thread-safe in-memory fallbacks.
- Enforces per-minute and daily sending quotas per channel.

### 19. Audit Logging
- All security-relevant actions (approvals, dispatch attempts, credential updates, status transitions, kill-switch toggles) record structured audit entries with actor ID, timestamp, and metadata.

### 20. Sensitive Information Exposure
- Production logs exclude passwords, bearer tokens, encryption keys, and raw webhook payloads.
- Repository `.gitignore` excludes `.env*`, `*.pem`, `*.key`, `*.dump`, and `*.sql` files.
