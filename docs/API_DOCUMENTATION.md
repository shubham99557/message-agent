# ActTrident REST API Reference

**Base URL**: `/api/v1`  
**Protocol**: HTTPS (TLS 1.3 recommended)  
**Authentication**: HTTP Bearer Token (`Authorization: Bearer <access_token>`)  
**Data Format**: `application/json` (except file uploads and streaming CSV exports)

---

## 1. Global Conventions

### 1.1 Authentication Header
Every authenticated request must include the JWT bearer token:
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 1.2 Standard Error Response
All error responses adhere to standard JSON error structures:
```json
{
  "detail": "Description of the validation or authorization error."
}
```

Common HTTP Status Codes:
- `200 OK`: Successful retrieval or synchronous operation.
- `201 Created`: Resource successfully created.
- `202 Accepted`: Asynchronous background task queued.
- `400 Bad Request`: Validation failure or prohibited transition.
- `401 Unauthorized`: Missing, expired, or revoked JWT token (including stale `tv` claim).
- `403 Forbidden`: Insufficient role or attempt to mutate an unowned resource.
- `404 Not Found`: Target entity does not exist.
- `409 Conflict`: Campaign state prevents dispatch or duplicate unique key.
- `423 Locked`: Outbound sending halted by active Global Kill Switch.
- `429 Too Many Requests`: Sending rate limit exceeded (burst or daily window).

---

## 2. Core API Endpoints

### 2.1 Authentication & User Access

#### `POST /auth/login`
Authenticates user credentials and issues short-lived access token and rotating refresh token.
- **Request Format**: `application/x-www-form-urlencoded`
- **Fields**:
  - `username` (string): User email address.
  - `password` (string): Password.
- **Response `200 OK`**:
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "a4f89d3c...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "director@acttrident.com",
    "full_name": "Sales Director",
    "role": "manager",
    "is_active": true,
    "created_at": "2026-11-14T10:00:00Z"
  }
}
```

#### `POST /auth/refresh`
Rotates an active refresh token and returns a new access/refresh pair.
- **Payload**: `{"refresh_token": "a4f89d3c..."}`
- **Response `200 OK`**: Returns new `access_token` and `refresh_token`.

#### `GET /auth/me`
Retrieves authenticated user profile.
- **Response `200 OK`**: Returns `UserResponse`.

---

### 2.2 Companies & Prospect Directory

#### `GET /companies`
Lists paginated company records with optional filters.
- **Query Parameters**:
  - `skip` (int, default: 0)
  - `limit` (int, default: 50, max: 200)
  - `city` (string, optional: e.g. "Siliguri", "Gangtok", "Patna", "Bhagalpur")
  - `industry` (string, optional)
  - `qualification_status` (string, optional)
  - `has_laptops` (bool, optional: filter for verified 5+ laptops)
  - `is_demo` (bool, optional: filter demo vs real records)
- **Response `200 OK`**:
```json
{
  "items": [
    {
      "id": 1,
      "name": "Siliguri Infotech Solutions",
      "website": "https://siliguriinfotech.example.com",
      "city": "Siliguri",
      "state": "West Bengal",
      "industry": "Software Development",
      "public_email": "contact@siliguriinfotech.example.com",
      "public_phone": "+91-353-2541001",
      "laptop_count_verified": 14,
      "laptop_count_evidence": "MCA corporate registry filing lists 18 active full-time technical personnel",
      "qualification_status": "High priority",
      "qualification_score": 85.0,
      "is_demo": false
    }
  ],
  "total": 48,
  "skip": 0,
  "limit": 50
}
```

#### `POST /companies/{id}/verify`
Records formal human evidence verification for fleet device count and decision maker.
- **Payload**:
```json
{
  "laptop_count_verified": 16,
  "laptop_count_evidence": "Confirmed via MCA filing and employee interviews",
  "decision_maker_name": "Amitabh Roy",
  "decision_maker_role": "Managing Director",
  "verification_method": "mca_filing",
  "notes": "Evidence verified from Ministry of Corporate Affairs FY25 filings"
}
```

#### `GET /companies/export/csv`
Streams CSV formatted table of verified company directory.

---

### 2.3 Research & Discovery

#### `POST /research/discover`
Executes targeted web search discovery across North Bengal, Sikkim, and Bihar regions.
- **Payload**:
```json
{
  "city": "Siliguri",
  "industry": "Software Development",
  "query": "IT companies and software agencies in Siliguri with laptops"
}
```
- **Response `200 OK`**: Returns array of `DiscoveredCompanyItem` with confidence scores and source URLs.

---

### 2.4 Campaigns & Lifecycle Orchestration

#### `POST /campaigns`
Creates an outreach campaign with multi-channel and rate-limit parameters.
- **Payload**:
```json
{
  "name": "Siliguri IT Cluster Q4",
  "objective": "Introduce ActTrident 90-day workspace evaluation to tech firms with 5+ laptops",
  "target_city": "Siliguri",
  "target_industry": "Software Development",
  "min_devices": 5,
  "min_score": 70.0,
  "allowed_channels": "email,whatsapp,linkedin",
  "daily_email_limit": 50,
  "daily_whatsapp_limit": 20,
  "sending_schedule": "09:00-18:00 IST Weekdays"
}
```

#### `POST /campaigns/{id}/recipients`
Attaches verified prospect companies to the campaign.
- **Payload**: `{"company_ids": [1, 2, 5]}`
- **Note**: Rejects demo fixture companies (`.example.com`) with `HTTP 400 Bad Request`.

#### `POST /campaigns/{id}/batch-draft`
Triggers AI draft generation for all pending campaign recipients.
- **Payload**:
```json
{
  "tone": "Professional consultative",
  "custom_notes": "Mention local Siliguri references and 90-day complimentary evaluation"
}
```

#### Lifecycle Actions
- `POST /campaigns/{id}/pause`: Suspends dispatch.
- `POST /campaigns/{id}/resume`: Resumes paused campaign.
- `POST /campaigns/{id}/stop`: Permanently stops campaign and purges pending outbox items.
- `POST /campaigns/{id}/enqueue-approved`: Enqueues approved drafts into transactional outbox.
- `POST /campaigns/{id}/dispatch-approved`: Flushes approved drafts through sender adapter.

---

### 2.5 Approval Queue & Governance

#### `GET /approvals/queue`
Retrieves pending drafts awaiting human review.
- **Query Parameters**: `status` ("draft", "approved", "rejected", "scheduled"), `campaign_id`, `skip`, `limit`.

#### `POST /approvals/approve/{draft_id}`
Binds cryptographic SHA256 content hash and approves message for delivery.
- **Role Requirement**: `admin` or `manager`.

#### `POST /approvals/reject/{draft_id}`
Rejects draft with documented operational reason.
- **Payload**: `{"reason": "Exaggerated claim regarding device compatibility"}`

#### `POST /approvals/schedule/{draft_id}`
Assigns explicit send timestamp.
- **Payload**: `{"scheduled_at": "2026-11-20T09:30:00Z"}`

#### `POST /approvals/regenerate/{draft_id}`
Prompts AI engine to re-generate draft with modified tone or guidance.
- **Payload**: `{"tone": "Short executive summary", "custom_notes": "Focus on data leak protection"}`

---

### 2.6 CRM Pipeline & Outreach

#### `GET /crm/leads`
Lists leads across the 7 pipeline stages (`new`, `contacted`, `replied`, `meeting_scheduled`, `trial_active`, `closed_won`, `closed_lost`, `opted_out`).

#### `PATCH /crm/leads/{id}/status`
Moves lead to new pipeline stage with notes and audit logging.
- **Payload**: `{"status": "meeting_scheduled", "notes": "Demo booked for next Tuesday at 11 AM"}`

#### `GET /crm/export/csv`
Streams full CSV export of leads, decision maker roles, device evidence, and trial status.

#### `POST /crm/opt-out`
Records prospect unsubscribe / opt-out and permanently suppresses identifier.
- **Payload**:
```json
{
  "identifier": "prospect@example.com",
  "channel": "all",
  "reason": "Requested removal via reply email"
}
```

---

### 2.7 Background Tasks & Queue Health

#### `GET /jobs/health`
Returns Redis connectivity status, Celery worker ping, and queue backlog counts.

#### `POST /jobs/trigger`
Triggers an autonomous task (e.g. `nightly_discovery`, `sync_gmail`, `process_outbox`).
- **Role Requirement**: `admin` or `manager`.

#### `GET /jobs/dlq` & `POST /jobs/dlq/{id}/retry`
Inspects dead-lettered tasks and triggers re-execution.

---

### 2.8 System Settings & Kill Switch

#### `GET /settings/kill-switch`
Returns boolean `active` status and `reason`.

#### `POST /settings/kill-switch`
Toggles outbound emergency kill switch.
- **Payload**: `{"active": true, "reason": "Operator maintenance window"}`
- **Role Requirement**: `admin` or `manager`.
