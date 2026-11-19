# Incident Response Runbook & Emergency Playbooks

**Platform**: ActTrident AI Sales Outreach & Automation  
**Classification**: Operational Security & Emergency Response Protocol  
**Audience**: On-Call Engineers, Site Reliability Engineers (SRE), Sales Operations Directors

---

## 1. Severity Classification Matrix

| Level | Definition | Response SLA | Immediate Action |
|---|---|:---:|---|
| **P0 (Critical)** | Active erroneous outbound sending storm, unauthorized message delivery, security breach, or compromised cryptographic secrets. | **< 5 minutes** | **Immediately trigger Global Outbound Kill Switch**. Page engineering lead. |
| **P1 (Major)** | Celery worker crash, Redis broker offline, database failover, or provider-wide delivery failure (e.g. Gmail 401 token revocation). | **< 15 minutes** | Pause active campaigns, inspect worker logs, switch to simulated fallback. |
| **P2 (Moderate)** | High bounce rate alert (> 5%), rate limit throttling (HTTP 429), or DLQ task failure backlog. | **< 1 hour** | Reduce campaign dispatch rates, inspect failed DLQ payloads, verify contact lists. |
| **P3 (Minor)** | Non-blocking UI glitch, slow query performance, or minor reporting discrepancy. | **< 1 business day** | Create issue in backlog, schedule for next maintenance release. |

---

## 2. Emergency Incident Protocol: Halting Outbound Traffic

In the event of an erroneous draft, unapproved messaging, or high bounce rate:

### Step 1: Trigger the Global Kill Switch Instantly
**Via Web UI**:
1. Log in to `https://sales.acttrident.com` with an `admin` or `manager` account.
2. Navigate to **Settings**.
3. Under the red banner, enter reason: `P0 Incident: Investigating outreach anomaly`.
4. Click **Stop All Outbound Sending**. The status turns red (`ALL SENDING HALTED`).

**Via API CLI** (if UI is inaccessible):
```bash
curl -X POST https://sales.acttrident.com/api/v1/settings/kill-switch \
     -H "Authorization: Bearer <admin_token>" \
     -H "Content-Type: application/json" \
     -d '{"active": true, "reason": "P0 Emergency API Halt"}'
```

**Direct Database Fallback** (if API server is down):
```bash
docker exec -it acttrident-postgres psql -U acttrident_user -d acttrident_db -c \
  "INSERT INTO system_settings (key, value) VALUES ('global_outbound_kill_switch', '{\"active\": true, \"reason\": \"Direct DB Emergency Halt\"}') ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;"
```

### Step 2: Stop Asynchronous Background Workers
```bash
docker compose -f docker-compose.prod.yml stop celery_worker celery_beat
```

---

## 3. Specific Emergency Playbooks

### Playbook 1: Accidental Outreach Storm / Wrong Campaign Sent
1. **Trigger Kill Switch** (Section 2).
2. **Purge Pending Outbox Rows**:
   ```sql
   UPDATE outbound_dispatch_outbox 
   SET status = 'cancelled', error_details = 'Cancelled during P0 incident' 
   WHERE status = 'pending';
   ```
3. **Audit Delivered Messages**:
   ```sql
   SELECT id, campaign_id, channel, provider_message_id, created_at 
   FROM outbound_dispatch_outbox 
   WHERE status = 'sent' AND created_at > NOW() - INTERVAL '1 hour';
   ```
4. **Draft Apology / Retraction**: If communications reached external prospects mistakenly, coordinate with the Sales Director to issue a polite manual clarification.

---

### Playbook 2: Provider Throttling / Rate Limit Block (Gmail / Meta)
1. **Symptom**: Outbox logs show HTTP 429 Too Many Requests or Meta error `rate_limit_hit`.
2. **Immediate Action**:
   - Pause the affected campaign via the UI or `POST /api/v1/campaigns/{id}/pause`.
   - Verify sliding window rate limits in `backend/app/services/email_sender_service.py` (burst limit is 10/min).
   - Check if external manual sends were conducted outside ActTrident on the same Google Workspace account.
3. **Remediation**:
   - Lower campaign `daily_email_limit` from 50 to 25.
   - Adjust Celery Beat outbox schedule from 60 seconds to 120 seconds.
   - Resume campaign when the provider throttle window clears (typically 1 hour).

---

### Playbook 3: Security Incident: Suspected JWT or Secret Leak
1. **Rotate User Token Versions (Instant Global Logout)**:
   ```sql
   -- Instantly invalidates all active JWT tokens across all users
   UPDATE users SET token_version = token_version + 1;
   ```
2. **Revoke All Active Refresh Tokens**:
   ```sql
   UPDATE refresh_tokens SET revoked_at = NOW() WHERE revoked_at IS NULL;
   ```
3. **Rotate Application Secrets**:
   - Generate a new `SECRET_KEY` via `openssl rand -hex 32`.
   - Update `.env` or container environment secrets.
   - Restart the application: `docker compose -f docker-compose.prod.yml restart app`.
4. **Review Audit Logs**:
   ```sql
   SELECT * FROM audit_logs WHERE created_at > NOW() - INTERVAL '24 hours' ORDER BY id DESC;
   ```

---

### Playbook 4: Database Connection Pool Exhaustion
1. **Symptom**: FastAPI returns HTTP 500 `QueuePool limit of size 5 overflow 10 reached`.
2. **Immediate Action**:
   - Inspect active PostgreSQL connections:
     ```bash
     docker exec -it acttrident-postgres psql -U acttrident_user -d acttrident_db -c \
       "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
     ```
3. **Remediation**:
   - Terminate idle connections if locked:
     ```sql
     SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND state_change < NOW() - INTERVAL '15 minutes';
     ```
   - Tune `backend/app/core/database.py` connection pool: increase `pool_size=20`, `max_overflow=10`, `pool_recycle=1800`.
   - Restart backend container.

---

## 5. Post-Incident Review (PIR) Protocol

Within 24 hours of closing a P0 or P1 incident, the on-call engineer must complete a Post-Incident Review:
1. **Summary of Incident**: Timeline from detection to resolution.
2. **Root Cause Analysis (5 Whys)**: Underlying technical or operational failure.
3. **Impact Assessment**: Number of prospects contacted, failed sends, or downtime duration.
4. **Action Items**: Preventative code fixes, regression tests, or monitoring alerts added to eliminate recurrence.
