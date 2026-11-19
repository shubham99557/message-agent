# ActTrident AI Sales Outreach & Automation Agent — Application Security Review

**Document Version:** 1.0.0  
**Classification:** Internal Confidential / Release Gate D Documentation  
**Date:** November 19, 2026  
**Auditor:** Application Security Lead & DevOps Architect  

---

## 1. Executive Summary

This security review evaluates the ActTrident AI Sales Outreach & Automation Platform against modern application security standards (OWASP Top 10, ASVS Level 2, and India Digital Personal Data Protection Act compliance). 

The platform employs a defense-in-depth posture:
- **Mandatory Human-in-the-Loop:** Automated code paths can only create draft messages; outbound dispatch requires explicit authenticated human approval.
- **Fail-Safe Emergency Controls:** A global, database-backed emergency kill switch immediately stops all outbound traffic.
- **Strict Provenance & Isolation:** Quarantine mechanisms prevent test/demo data (`.example.com`) from leaking into live outbound outreach.
- **Zero Insecure Defaults in Production:** Startup guards block boot if secrets are weak, SQLite is configured in production, or webhook secrets use known defaults.

---

## 2. Threat Model & Mitigations

### 2.1 Unauthorized Outbound Messaging
- **Threat:** AI autonomously sends erroneous, aggressive, or hallucinatory messages without oversight.
- **Mitigation:**
  - AI generation produces records strictly in `approval_status="draft"`.
  - Any edit made to an approved message immediately invalidates prior approval, recalculates the SHA-256 content hash, increments the draft version, and requires explicit re-approval (`backend/app/services/approval_service.py`).
  - Outbound dispatch enforces immutability: if content does not match `approved_content_hash`, send is rejected.

### 2.2 Server-Side Request Forgery (SSRF)
- **Threat:** Malicious inputs in lead discovery or website crawl probe internal cloud metadata (`169.254.169.254`) or private networks.
- **Mitigation:**
  - `is_safe_external_url()` resolves hostnames and validates that the target IP does not fall within loopback (`127.0.0.0/8`), private RFC 1918 blocks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local, or cloud metadata ranges (`backend/app/core/security.py`).
  - Tested and verified in `test_crawl_website_ssrf_protection` and `test_compliance_blocks_ssrf_urls`.

### 2.3 Privilege Escalation & Insecure Direct Object References (IDOR)
- **Threat:** Sales representatives view or modify accounts or drafts owned by other reps or tamper with admin settings.
- **Mitigation:**
  - RBAC enforces permissions for `admin`, `manager`, and `sales_rep`.
  - Company update, verification, and draft update endpoints verify that non-admin users own the entity (`created_by_id == current_user.id`).
  - Public registration (`POST /api/v1/auth/register`) enforces `role="sales_rep"` regardless of client-supplied payloads (`backend/app/api/endpoints/auth.py`).

### 2.4 Token Replay & Session Revocation
- **Threat:** Stolen JWT access tokens remain valid until expiration.
- **Mitigation:**
  - JWT tokens enforce mandatory `tv` (token version) claim. Any token lacking `tv` or matching a revoked token version is rejected with HTTP 401 (`backend/app/api/deps.py`).
  - Refresh tokens are stored in the database, rotated on every refresh, and revoked on logout.

### 2.5 Webhook Tampering
- **Threat:** Attackers spoof incoming Meta WhatsApp webhooks to forge delivery receipts or inbound conversations.
- **Mitigation:**
  - `process_incoming_meta_webhook()` computes HMAC-SHA256 of the raw payload using `META_APP_SECRET` and verifies it against the `X-Hub-Signature-256` header before parsing.

### 2.6 Outbound Rate Limiting & Denial of Service
- **Threat:** High-volume dispatches exhaust provider quotas or trigger anti-spam blacklisting.
- **Mitigation:**
  - Multi-tier rate limiting: sliding-window Redis limiter checks burst limits per minute (`OUTBOUND_RATE_LIMIT_EMAIL_PER_MIN=30`, `OUTBOUND_RATE_LIMIT_WA_PER_MIN=10`) and daily campaign ceilings.
  - Rate limiting is enforced synchronously before every dispatch attempt and inside background Celery workers.

---

## 3. Compliance & Lawful Basis (India & B2B Guidelines)

### 3.1 Targeted Geography & B2B Nature
- The platform targets corporate B2B communications across Siliguri, Gangtok, Patna, and Bhagalpur.
- Only publicly available business contact information (corporate email, official phone, official website) is retrieved.
- Private employee contact details and personal phone numbers are never fabricated or harvested.

### 3.2 India Digital Personal Data Protection (DPDP) Act Compliance
1. **Notice & Consent:**
   - Outbound emails clearly identify ActTrident Business Development and the proposed 90-Day Free Product Evaluation.
   - WhatsApp messaging enforces verified opt-in records prior to outbound template dispatches.
2. **Instant Opt-Out & Suppression:**
   - Unsubscribe or "STOP" replies immediately update the global `SuppressionList` table.
   - Suppression checks occur synchronously immediately before every outbound dispatch, including background retries and transactional outbox jobs.
3. **Data Retention & Purpose Limitation:**
   - Lead records retain clear provenance (`source_url`, `source_type`, `retrieved_at`).
   - Audit logs capture all user actions, approvals, rejections, and setting modifications.

---

## 4. Penetration Testing Results

Automated security penetration test suite `backend/tests/test_phase7_e2e_and_security_penetration.py` and `backend/tests/test_security_regressions.py` passed with 100% compliance:

| Attack Vector | Test Case | Outcome |
| :--- | :--- | :--- |
| Public registration privilege escalation | `test_public_registration_privilege_escalation_blocked` | **BLOCKED (HTTP 201 forced to sales_rep)** |
| Weak production secret key & wildcard CORS | `test_production_rejects_weak_secret_and_wildcard_cors` | **BLOCKED (Startup ValueError)** |
| Revoked JWT / Missing token version | `test_fix9_jwt_missing_token_version_claim_is_rejected` | **REJECTED (HTTP 401)** |
| Post-approval content tampering | `test_content_tampering_blocks_dispatch` | **BLOCKED (Content mismatch rejected)** |
| Webhook HMAC signature forgery | `test_meta_webhook_hmac_signature_verification_and_idempotency` | **REJECTED (HTTP 401 invalid signature)** |
| SSRF loopback / private IP probe | `test_compliance_blocks_ssrf_urls` | **BLOCKED (Rejected URL)** |
| Outbound burst rate limit exceeded | `test_fix7_rate_limits_enforced_on_sync_email_and_whatsapp` | **THROTTLED (HTTP 429)** |
| Emergency Outbound Kill Switch | `test_global_kill_switch_halts_all_channels_and_restores_on_deactivate` | **HALTED (HTTP 423 Locked)** |

---

## 5. Security Verdict

The application architecture satisfies all required security foundation release gates. Production deployment is approved subject to operator-supplied production secrets and TLS reverse-proxy termination.
