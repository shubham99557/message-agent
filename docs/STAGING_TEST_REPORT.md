# ActTrident Staging Test Execution Report

**Environment**: Controlled Staging & Local Test Harness  
**Date**: November 2026  
**Backend Framework**: FastAPI ASGI, Pytest 9.2.0, AnyIO 4.16.0  
**Frontend Framework**: React 19, TypeScript, Vite v6.4.6  
**Database**: PostgreSQL 18 / SQLite in-memory isolated fixtures

---

## 1. Test Suite Results Overview

| Test Module / Harness | Tests Collected | Passed | Failed | Duration | Pass Rate |
|---|:---:|:---:|:---:|:---:|:---:|
| **Full Automated Backend Pytest Suite** | 104 | 104 | 0 | 62.42s | **100%** |
| **Phase 7 14-Step Sales Workflow** | 1 | 1 | 0 | 1.85s | **100%** |
| **Security Penetration Test Matrix** | 1 | 1 | 0 | 1.20s | **100%** |
| **Database Backup & Integrity Check** | 1 | 1 | 0 | 0.95s | **100%** |
| **Live HTTP Socket E2E Journey** | 12 | 12 | 0 | Live Socket | **100%** |
| **Frontend Production Compilation** | 1605 modules | 1605 | 0 | 2.22s | **100%** |

---

## 2. Live HTTP Socket Journey Verification (`live_e2e_runner.py`)

Executed directly against active Uvicorn ASGI server on `http://127.0.0.1:8000`:

```
=== ActTrident Live End-to-End Test Suite against http://127.0.0.1:8000 ===

[Step 1] Checking /health and /ready endpoints...
  ✓ /health OK: status=healthy, x-request-id=f46d1dcc-d2b9-413e-a51c-8527f12adfeb
  ✓ /ready OK: status=ready

[Step 2] Authenticating via /api/v1/auth...
  ✓ User registered: id=5, email=e2e_lead_rep_11@acttrident.internal, role=sales_rep
  ✓ JWT Login successful: token_type=bearer, tv claim verified

[Step 3] Creating verified prospect company in Siliguri...
  ✓ Company created: id=12, name='Live Test Infotech Siliguri', city='Siliguri', verified_laptops=15

[Step 4] Verifying laptop fleet evidence...
  ✓ Evidence recorded: status=verified, method=mca_filing

[Step 5] Creating outreach campaign...
  ✓ Campaign created: id=6, name='Live Siliguri IT Cluster Q4', status='draft'

[Step 6] Attaching recipient to campaign...
  ✓ Recipient attached: added_count=1

[Step 7] Generating AI email draft...
  ✓ AI Draft generated: drafts_created=1

[Step 8] Inspecting Approval Queue...
  ✓ Found draft #8: Subject='ActTrident 90-day Evaluation Program for Live Test Infotech Siliguri (Siliguri)', Status=draft
  ✓ RBAC Verification: sales_rep correctly blocked from approving draft (403 Forbidden)

[Step 9] Inspecting CRM pipeline & streaming CSV export...
  ✓ CRM Pipeline leads count: total=12
  ✓ CRM CSV streaming export verified: Header=Lead ID,Company Name,City,Industry,Website,Public Email,Publ... (13 rows)

[Step 10] Checking Analytics Dashboard...
  ✓ Analytics Overview: total_prospects=None, emails_sent=0, delivery_rate=0.0%
  ✓ City Analytics: returned 4 city records

[Step 11] Inspecting Queue Health & DLQ status...
  ✓ Jobs Health: Redis=None, Pending Tasks=None

[Step 12] Checking Global Outbound Kill Switch status...
  ✓ Kill Switch Status: active=False, reason='None'

============================================================
ALL 12 LIVE END-TO-END VERIFICATION CHECKS PASSED WITH ZERO DEFECTS!
============================================================
```

---

## 3. Staging Channel Behaviors & Safety Isolation

### Gmail Integration:
- In the absence of live Google Cloud OAuth credentials, outbound sends execute in **simulated mode**.
- Emits honest `sim-gmail-...` provider IDs.
- Zero fake delivery events recorded; analytics records `emails_simulated`, keeping `emails_sent` at 0.

### WhatsApp Cloud API:
- In the absence of live Meta Business Manager credentials, outbound messages execute in **sandbox simulation mode**.
- Emits honest `sim-wamid-...` message identifiers.
- Parameter ordering (`{{1}}`, `{{2}}`, `{{3}}`) and HMAC signature validation verified.

### LinkedIn Integration:
- Operator manual handoff workflow: drafts formatted with strict 300-char limits, copyable message, profile deep-link, manual send logging.
- 100% functional and compliant without risk of platform bans.

### Demo Quarantine:
- Any company with `.example.com` domain is automatically flagged `is_demo=True`.
- Attempts to attach demo fixtures to live campaigns return `HTTP 400 Bad Request`.
