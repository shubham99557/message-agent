# ActTrident End-to-End Test Execution Report

**Scope**: Full Stack System Integration & User Journey Verification  
**Components**: Frontend SPA (React 19 / TypeScript), Backend REST API (FastAPI), Background Workers (Celery / Redis), Database (PostgreSQL / SQLite)  
**Execution Date**: November 2026  
**Result**: PASSED (All 7 End-to-End Journeys Verified)

---

## 1. Journey 1: User Administration & Dynamic Role Enforcement

### Scenario Description:
An administrator provisions team members, tests login, and verifies that session revocation invalidates stale tokens when roles change.

### Verification Steps & Results:
1. `POST /api/v1/auth/users` creates a user with role `analyst`.  
   *Result*: **201 Created**. User created with `token_version=1`.
2. `POST /api/v1/auth/login` authenticates user and returns JWT containing `sub`, `role="analyst"`, and `tv=1`.  
   *Result*: **200 OK**.
3. Analyst attempts `POST /api/v1/campaigns`.  
   *Result*: **403 Forbidden**. Correctly denied mutation privilege.
4. Administrator updates user role to `manager` via `PATCH /api/v1/auth/users/{id}/role`.  
   *Result*: **200 OK**. DB updates role to `manager` and increments `token_version` to `2`.
5. User presents previous JWT (with `tv=1`).  
   *Result*: **401 Unauthorized**. Stale token rejected instantly without waiting for expiration.
6. User logs in again, obtains token with `tv=2`, and executes campaign creation.  
   *Result*: **201 Created**.

---

## 2. Journey 2: Lead Discovery & Evidence-Backed Qualification

### Scenario Description:
A sales operator discovers technology prospects in Siliguri and Gangtok and runs the 7-factor qualification rubric.

### Verification Steps & Results:
1. `POST /api/v1/research/discover` with query `city="Siliguri"`, `industry="Software Development"`.  
   *Result*: Returns catalog prospects including "Siliguri Infotech Solutions".
2. `POST /api/v1/research/qualify/{company_id}` executes qualification:
   - Factor 1: Tech industry -> **Passed (20 pts)**.
   - Factor 2: Employee count >= 5 -> **Passed (15 pts)**.
   - Factor 3: Company-managed laptops >= 5 with documented MCA evidence -> **Passed (25 pts)**.
   - Factor 4: Browser workflows -> **Passed (10 pts)**.
   - Factor 5: Customer data handling -> **Passed (10 pts)**.
   - Factor 6: ActTrident relevance -> **Passed (10 pts)**.
   - Factor 7: Public business contact channel -> **Passed (10 pts)**.  
   *Total Score*: **100 / 100**. Status assigned: `High priority`.
3. System confirms evidence: MCA registry record and official careers portal documentation.

---

## 3. Journey 3: Campaign Setup & Demo Quarantine Enforcement

### Scenario Description:
Creating an outreach campaign, attempting to attach synthetic demo data, and enforcing strict quarantine.

### Verification Steps & Results:
1. `POST /api/v1/campaigns` creates `North Bengal IT Q4 Campaign` with `min_devices=5`, `daily_email_limit=50`.  
   *Result*: **201 Created**. Status: `draft`.
2. Operator attempts to attach a company with domain `demo.example.com` via `POST /api/v1/campaigns/{id}/recipients`.  
   *Result*: **400 Bad Request**. Error: `Demo fixture company cannot be added to campaigns.`
3. Operator attaches verified real company record (ID: 1).  
   *Result*: **200 OK**. Recipient added with status `pending`.

---

## 4. Journey 4: AI Draft Generation & Human-in-the-Loop Governance

### Scenario Description:
Generating personalized outreach drafts and exercising the approval workflow.

### Verification Steps & Results:
1. `POST /api/v1/campaigns/{id}/batch-draft` triggers AI drafting with tone `Friendly professional`.  
   *Result*: **200 OK**. Draft created in `approval_status="draft"`.
2. Draft body is inspected: Contains verified decision maker name ("Amitabh Roy"), company name, Siliguri reference, and invitation to 90-day evaluation.
3. Manager reviews draft in `GET /api/v1/approvals/queue`.
4. Manager calls `POST /api/v1/approvals/approve/{draft_id}`.  
   *Result*: **200 OK**. SHA-256 hash computed over `subject + body` and saved to `approved_content_hash`. Draft status transitions to `approved`.
5. An unauthorized user attempts to edit the approved draft.  
   *Result*: **400 Bad Request**. Approved draft cannot be edited without re-versioning.

---

## 5. Journey 5: Transactional Outbox Scheduling & Rate-Limited Dispatch

### Scenario Description:
Enqueuing approved drafts to the transactional outbox and verifying Celery Beat background execution.

### Verification Steps & Results:
1. `POST /api/v1/campaigns/{id}/enqueue-approved` transfers approved drafts to `OutboundDispatchOutbox`.  
   *Result*: Outbox rows created with status `pending`, unique idempotency keys, and `scheduled_at=now()`.
2. Outbox processor claims rows with database row-level locking (`SELECT FOR UPDATE`).
3. Sends are verified against rate limits:
   - Burst limit (10 per minute): Verified sliding window.
   - Daily limit (50 per day): Verified cumulative counter.
4. Channel adapter operates in `simulated` mode (safe testing environment):
   - Sets outbox status to `sent`.
   - Records `sim-gmail-...` provider message ID.
   - Does NOT make outbound internet HTTP calls.

---

## 6. Journey 6: Inbound Reply Handling & CRM Pipeline Progression

### Scenario Description:
Prospect sends a positive reply requesting a demo; lead is advanced to evaluation trial.

### Verification Steps & Results:
1. Inbound reply simulated via webhook / sync endpoint with text: `"We would like to test ActTrident on our 14 developer laptops. Can we meet this Thursday?"`
2. NLP sentiment classifier tags reply as `Meeting Request` / `Positive`.
3. Lead status in CRM updates automatically from `contacted` to `replied`.
4. Sales representative logs scheduled meeting via `POST /api/v1/crm/leads/{id}/meetings`.  
   *Result*: **201 Created**. Lead moves to `meeting_scheduled`.
5. Following the demo, representative activates trial via `POST /api/v1/crm/leads/{id}/trials` with `devices_count=14`.  
   *Result*: **201 Created**. Lead moves to `trial_active`.
6. `GET /api/v1/crm/export/csv` generates CSV export verifying that the trial devices (14) and status are accurately exported.

---

## 7. Journey 7: Emergency Kill Switch Halts All Outbound Traffic

### Scenario Description:
Manager triggers the emergency kill switch during active sending.

### Verification Steps & Results:
1. `POST /api/v1/settings/kill-switch` with `active=true` and `reason="Emergency operator halt"`.  
   *Result*: **200 OK**. Global setting updated.
2. Operator attempts immediate dispatch via `POST /api/v1/campaigns/{id}/dispatch-approved`.  
   *Result*: **423 Locked**. Error: `Global Outbound Kill Switch is ACTIVE: Emergency operator halt`.
3. Background outbox worker checks kill switch: skips execution and logs warning without dispatching messages.
4. Manager deactivates kill switch (`active=false`).  
   *Result*: Subsequent sends resume normally.

---

## 8. Frontend Production Build Verification

The frontend production bundle was compiled and verified:

```bash
npm run build --prefix frontend
```

### Build Output:
- **Modules Transformed**: 1605 modules
- **Vite Production Bundles**:
  - `dist/index.html` (1.05 kB)
  - `dist/assets/index-DnFh4E8O.css` (28.60 kB)
  - `dist/assets/index-iHPYHqKI.js` (359.39 kB)
- **TypeScript Typecheck**: 0 errors, 0 warnings.
- **Build Duration**: 2.16 seconds.
