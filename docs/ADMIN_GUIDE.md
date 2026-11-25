# ActTrident Administrator & Operations Guide

**Audience**: Super Administrators, DevOps Engineers, Security Officers  
**Access Level**: `admin` Role

---

## 1. User Provisioning & RBAC Management

ActTrident enforces strict Role-Based Access Control backed by live database verification and instantaneous session revocation.

### 1.1 Provisioning New Users
1. Log in with an `admin` account and navigate to **Settings > User Access & Role Management**.
2. Click **Add User** (or use `POST /api/v1/auth/users`).
3. Fill in the user profile:
   - **Full Name**: E.g. `Ananya Sen`
   - **Email**: Corporate email address (e.g. `ananya@acttrident.com`).
   - **Initial Password**: Must satisfy the password policy (>= 8 chars, 1 uppercase, 1 lowercase, 1 number).
   - **Assigned Role**: Select from:
     - `admin`: Super Administrator (Infrastructure, credentials, kill switch).
     - `manager`: Campaign Manager (Approvals, campaigns, dispatch, CRM).
     - `sales_rep`: Sales Operator (Discovery, draft composition, assigned leads).
     - `analyst`: Read-Only Analyst (Reports, analytics, CSV exports, no mutations).
4. Click **Create User**.

### 1.2 Promoting, Demoting & Deactivating Accounts
- **Role Changes**: Selecting a new role in the table immediately rotates the user's `token_version` integer in the database. Any existing JWTs bearing the old role claim are rejected on their subsequent request (`HTTP 401 Unauthorized`).
- **Account Deactivation**: Clicking **Deactivate** immediately revokes all active refresh tokens and increments the token version. The user is logged out instantly across all browsers and devices.

---

## 2. Emergency Global Outbound Kill Switch

The Global Outbound Kill Switch is an emergency circuit breaker designed to halt all outbound communications if a defect, misconfiguration, or compliance issue is detected.

### 2.1 What the Kill Switch Halts
When activated, the kill switch immediately blocks:
- **Email Outreach**: Synchronous and Celery-driven Gmail sends.
- **WhatsApp Outreach**: Outbound Meta Graph API template and freeform calls.
- **LinkedIn Messaging**: Operator handoff copy workflows and manual dispatch logging.
- **Transactional Outbox**: Celery Beat background flushes return early without claiming rows.
- **Scheduled Follow-ups**: Automated reminder queues are paused.
- Any manual or scheduled send request returns `HTTP 423 Locked: Global Outbound Kill Switch is ACTIVE`.

### 2.2 How to Activate / Resume
1. In **Settings**, locate the red **Emergency Kill Switch** banner.
2. Enter an operational reason (e.g. `Investigating email bounce spike on Siliguri campaign`).
3. Click **Stop All Outbound Sending**. The status indicator turns red (`ALL SENDING HALTED`).
4. To resume operations after resolving the issue:
   - Click **Resume Sending**. The status indicator turns green (`Normal Operation`).

---

## 3. Global Suppression List & Compliance Registry

ActTrident maintains an immutable suppression registry to honor opt-out and bounce events across all channels.

### 3.1 Automatic vs. Manual Additions
- **Automatic**: Inbound WhatsApp `STOP` replies, Gmail bounce notices (550 Mailbox Unavailable), and unsubscribe link clicks automatically register in the suppression list.
- **Manual**: Administrators and managers can manually suppress an email address, phone number, or domain by submitting the **Record Opt-Out** dialog.

### 3.2 Inspecting Suppressed Identifiers
1. Navigate to **Settings > Global Suppression List**.
2. Review suppressed contacts, identifying the channel (`email`, `whatsapp`, or `all`), reason (`user_opt_out`, `hard_bounce`, `dnc_request`), and timestamp.
3. Suppressed identifiers are permanently excluded from campaign recipient lists and discovery imports.

---

## 4. Tamper-Evident Audit Logging

Every security-sensitive and operational action is recorded to the immutable `audit_logs` table.

### 4.1 Viewing Audit Logs
1. Navigate to **Settings > System Activity Audit Log**.
2. Filter by:
   - Action type (`create_campaign`, `approve_email_draft`, `toggle_kill_switch`, `admin_create_user`, `admin_update_user_role`, etc.)
   - User ID or entity ID
3. Inspect the payload details (shows timestamp, actor email, IP address, and changed attributes).
4. Audit log rows cannot be updated or deleted via API endpoints.

---

## 5. Background Queue Health & Dead Letter Queue (DLQ)

ActTrident utilizes Celery and Redis to handle asynchronous discovery, outbox flushes, and Gmail synchronization.

### 5.1 Monitoring Queue Health
1. Navigate to **Settings > Queue Health** (or `GET /api/v1/jobs/health`).
2. Verify:
   - **Redis Status**: `online` (Ping response <= 5ms).
   - **Celery Worker Ping**: Returns active worker hostname and pool concurrency.
   - **Queue Backlog**: Number of pending, running, and completed tasks.

### 5.2 Inspecting & Replaying the DLQ
If a background job encounters an unhandled exception or exhausts its 3 retry attempts:
1. The task transitions to `failed` and is recorded in `DeadLetterTask`.
2. Inspect the failed job in the DLQ view to review the stack trace and original payload.
3. After addressing the root cause (e.g. updating an expired API credential), click **Retry Task** to re-inject the payload into the execution queue.
