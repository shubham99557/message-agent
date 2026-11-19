# ActTrident AI Outreach Platform — Production Operations Runbook

**Document Version:** 2.0.0  
**Target Environment:** Production Candidate  
**Last Verified:** 2026-11-19  
**Security Baseline:** Zero Live Dispatch Default (`LIVE_SEND_ENABLED=false`), DPDP Act 2023 Compliant, TRAI TCCCPR 2018 Compliant.

---

## 1. System Overview & Architecture

ActTrident is an AI-powered B2B sales automation and intelligence platform built on:
- **Backend**: FastAPI (Python 3.14 / ASGI) asynchronous REST API with SQLAlchemy 2.0.
- **Frontend**: React 18 / TypeScript / Vite / Tailwind CSS with Lucide Icons.
- **Persistence**: PostgreSQL 16 (Relational Database) with Alembic migration versioning.
- **Queues & Caching**: Redis 7.x (Message Broker & Cache) and Celery distributed task workers.
- **Channel Adapters**:
  - **Email**: Google Workspace / Gmail REST API (OAuth 2.0 PKCE) + SMTP Fallback.
  - **WhatsApp**: Meta WhatsApp Cloud API v22.0 (Permanent System User Token + Webhooks).
  - **LinkedIn**: Operator-assisted manual handoff with deep links complying with ToS Section 8.2.
- **Discovery**: Tavily AI Search, SerpAPI Google Maps, and OpenStreetMap Nominatim with rate limiting.

---

## 2. Pre-Flight Verification & System Health Checks

### 2.1 HTTP Health Probes
ActTrident exposes standard health endpoints for load balancers (Nginx / ALB) and container orchestrators:

| Endpoint | Method | Expected HTTP | Payload / Check Description |
| :--- | :---: | :---: | :--- |
| `/health` | `GET` | `200 OK` | Fast liveness probe verifying ASGI loop is responsive. |
| `/ready` | `GET` | `200 OK` | Readiness probe verifying PostgreSQL and Redis connections. |
| `/api/v1/jobs/health` | `GET` | `200 OK` | Celery task queue health, Redis ping latency, and pending tasks. |

**Command Line Check:**
```bash
curl -f http://127.0.0.1:8000/health
curl -f http://127.0.0.1:8000/ready
```

### 2.2 Background Services Status
Ensure all system components are active before enabling campaigns:
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check Redis status
sudo systemctl status redis-server

# Check Celery Worker
sudo systemctl status celery-worker

# Check Celery Beat Scheduler
sudo systemctl status celery-beat
```

---

## 3. Outbound Outreach Safety & Emergency Kill Switch

### 3.1 Safety Guarantees
1. **Simulation Default:** The system runs in simulation mode unless `LIVE_SEND_ENABLED=true` is explicitly set in production environment variables.
2. **Mandatory Human Approval:** No email or WhatsApp message can be dispatched without an authorized manager's explicit digital sign-off and SHA-256 immutable content hash match.
3. **Real-Time Suppression Interceptor:** Immediately prior to any dispatch, the recipient identifier is checked against the global suppression list. If suppressed, the send is aborted immediately.

### 3.2 Emergency Global Kill Switch
If unexpected activity, domain reputation alerts, or compliance inquiries occur, operators can halt all outbound dispatches instantaneously.

- **Via Web UI:** Navigate to **Settings → Outreach Safety Controls → Emergency Outbound Kill Switch** and toggle to **ACTIVE**.
- **Via REST API (Admin/Manager JWT Required):**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/settings/kill-switch \
  -H "Authorization: Bearer <ADMIN_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"active": true, "reason": "Operator-initiated emergency freeze"}'
```
- **Verification:** Check kill switch status:
```bash
curl http://127.0.0.1:8000/api/v1/settings/kill-switch
# Returns: {"active": true, "reason": "Operator-initiated emergency freeze", "updated_at": "..."}
```

---

## 4. Multi-Channel Integration Management

### 4.1 Gmail OAuth 2.0 Integration
- **Authorization Flow:** Initiated in **Settings → Channels → Connect Gmail** using PKCE with least-privilege scopes (`gmail.send`, `gmail.readonly`, `userinfo.email`).
- **Token Refresh:** Handled automatically in `backend/app/integrations/gmail_adapter.py`. If a refresh token is revoked or expires, connection status flips to `reauth_required`.
- **Operator Action on `reauth_required`:**
  1. Open ActTrident UI → Settings → Channels.
  2. Click **Reconnect Gmail**.
  3. Sign in to authorized Google Workspace account and grant permissions.

### 4.2 Meta WhatsApp Cloud API Integration
- **Prerequisites:** Meta Business Manager account with verified business and phone number.
- **Required Credentials:**
  - `META_WA_PHONE_NUMBER_ID`
  - `META_WA_ACCESS_TOKEN` (Permanent System User Token)
  - `META_WA_APP_SECRET` (For webhook HMAC-SHA256 signature verification)
  - `META_WA_VERIFY_TOKEN` (For Meta webhook challenge verification)
- **Webhook Endpoint:** `POST /api/v1/whatsapp/webhook`
  - All incoming payloads verify `X-Hub-Signature-256`. Untrusted or forged signatures return `403 Forbidden`.
- **Template Synchronization:** Operators must sync approved message templates before launching campaigns:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/whatsapp/templates/sync \
  -H "Authorization: Bearer <MANAGER_JWT_TOKEN>"
```

### 4.3 LinkedIn Compliant Manual Workflow
- In accordance with LinkedIn User Agreement Section 8.2, ActTrident prohibits automated browser bots or private API scraping.
- **Operator Procedure:**
  1. ActTrident AI prepares personalized connection note or InMail copy.
  2. Sales Rep reviews and clicks **Open LinkedIn Profile**.
  3. Message is pasted and sent manually via the rep's authorized browser session.
  4. Rep clicks **Mark as Sent** in ActTrident to transition CRM state.

---

## 5. Domain Reputation & Mailbox Warm-Up Schedule

To prevent domain blacklisting and maintain high sender deliverability, the automated warm-up rate limiter enforces strict daily sending caps:

| Mailbox Active Age | Maximum Daily Send Cap | Operational Focus |
| :--- | :---: | :--- |
| **Days 1 – 7** | **20 emails/day** | Warm-up phase; focus on highest-fit leads. |
| **Days 8 – 14** | **50 emails/day** | Gradual volume ramp; monitor bounce rate. |
| **Days 15 – 21** | **100 emails/day** | Established domain; ensure spam complaints <0.1%. |
| **Days 22+** | **Max 200 emails/day** | Mature cold outreach cap per mailbox. |

**Monitoring Domain Health:**
- Check Google Postmaster Tools weekly for domain reputation (High / Medium / Low / Bad).
- If spam complaint rate exceeds 0.2%, pause campaigns immediately via the Campaign Settings.

---

## 6. Regulatory Compliance & Data Privacy Operations

### 6.1 India DPDP Act 2023 Section 12 — Right to Erasure ("Right to be Forgotten")
When an individual requests complete erasure of their personal data:
1. Operator navigates to **CRM → Lead Details → DPDP Data Erasure** (or calls `/api/v1/crm/erasure`).
2. Payload submits the recipient identifier (email or phone).
3. The system executes `execute_dpdp_erasure`:
   - Permanently anonymizes name, email, and phone in Company, Contact, and Lead records.
   - Retains the identifier in the global `suppression_list` with reason `dpdp_right_to_erasure`.
   - Records an immutable audit log entry.
4. Output confirms count of sanitized records.

### 6.2 Public RFC 8058 One-Click Opt-Out
- Every outbound email includes standard headers:
  - `List-Unsubscribe: <https://acttrident.ai/api/v1/crm/public/opt-out?email=...>`
  - `List-Unsubscribe-Post: List-Unsubscribe=One-Click`
- Inbound requests to `/api/v1/crm/public/opt-out` (GET or POST) require zero login credentials and immediately populate the suppression list.

### 6.3 TRAI Commercial Hours Curfew (TCCCPR 2018)
- Automated outreach to Indian telephone numbers (+91) is strictly restricted to **09:00 AM to 09:00 PM IST** (03:30 to 15:30 UTC).
- The pre-send interceptor automatically blocks sends attempted outside this window with error code `TRAI_COMMERCIAL_HOURS_RESTRICTION`.

---

## 7. Celery Queue & Dead-Letter Queue (DLQ) Management

When background tasks fail repeatedly:
1. Tasks retry up to 3 times with exponential backoff (initial delay 5s, backoff factor 2.0).
2. If retries are exhausted, the task is routed to the Dead-Letter Queue table (`dead_letter_tasks`).
3. **Inspecting DLQ via API:**
```bash
curl http://127.0.0.1:8000/api/v1/jobs/dlq -H "Authorization: Bearer <ADMIN_JWT_TOKEN>"
```
4. **Replaying Dead-Letter Tasks:**
   - Operators can inspect the stored exception traceback, fix the root cause (e.g., restore network access to external provider), and trigger a replay:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/dlq/{task_id}/retry \
  -H "Authorization: Bearer <ADMIN_JWT_TOKEN>"
```

---

## 8. Backup, Restore & Disaster Recovery

### 8.1 Automated PostgreSQL Backup
Run daily via cron:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/acttrident"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
mkdir -p "$BACKUP_DIR"
pg_dump -U acttrident_user -d acttrident_db -F c -b -v -f "$BACKUP_DIR/acttrident_backup_$TIMESTAMP.dump"
# Retain backups for 30 days
find "$BACKUP_DIR" -type f -name "*.dump" -mtime +30 -exec rm {} \;
```

### 8.2 Database Restore Procedure
In the event of database corruption or hardware failure:
```bash
# 1. Stop backend services
sudo systemctl stop acttrident-backend celery-worker

# 2. Restore database from dump
pg_restore -U acttrident_user -d acttrident_db -v -c /var/backups/acttrident/acttrident_backup_TIMESTAMP.dump

# 3. Apply any pending Alembic migrations
cd /opt/acttrident/backend
alembic upgrade head

# 4. Restart backend services
sudo systemctl start acttrident-backend celery-worker
```

---

## 9. Operator Incident Escalation Matrix

| Incident Severity | Trigger Condition | Immediate Containment | Resolution SLA |
| :--- | :--- | :--- | :--- |
| **SEV-1 (Critical)** | Unintended live sends; data breach allegation; DB down. | Activate Global Kill Switch; halt Celery workers. | < 1 hour |
| **SEV-2 (High)** | Upstream provider 429 quota exhaustion; webhook signature failures. | Pause affected campaign; verify API credentials. | < 4 hours |
| **SEV-3 (Medium)** | Nominatim rate limit throttling; individual prospect opt-out dispute. | Add recipient to suppression list; review Redis cache. | < 24 hours |
| **SEV-4 (Low)** | Minor UI styling glitch; non-blocking search latency. | Log issue in tracker; schedule for sprint cycle. | Next release |

---
*Runbook Approved for Production Operations.*
