# Role & Permission Matrix (RBAC)

**Project**: ActTrident AI Outreach & Sales Automation  
**Enforcement Mechanism**: Database-backed user role evaluation in FastAPI `Depends(require_role([...]))` and frontend role-based view rendering.  
**Roles Defined**: `admin` (Super Admin), `manager` (Campaign Manager), `sales_rep` (Sales Operator), `analyst` (Read-Only Analyst).

---

## 1. High-Level Role Definitions

| Role | Hierarchy Level | Primary Responsibility | Mutation Permissions |
|---|---|---|---|
| **`admin`** | Level 1 (Highest) | System infrastructure, OAuth credentials, user accounts, system configuration, kill switch, compliance. | Full system read/write across all modules. |
| **`manager`** | Level 2 | Campaign lifecycle, approval queue governance, CRM oversight, manual job triggers, kill switch. | Full outreach & campaign management. Cannot edit user roles or API credentials. |
| **`sales_rep`** | Level 3 | Prospect research, company management, draft composition, stage updates for assigned leads. | Self-owned records only. Cannot approve messages, cannot execute bulk sends, cannot touch system settings. |
| **`analyst`** | Level 4 | Performance monitoring, market intelligence, funnel analysis, CRM data extraction. | **Read-only across the platform**. Zero mutation or dispatch capabilities. |

---

## 2. Endpoint-by-Endpoint Permission Matrix

### 2.1 Authentication & User Administration (`/api/v1/auth`)

| Endpoint | Method | Description | `admin` | `manager` | `sales_rep` | `analyst` |
|---|---|---|:---:|:---:|:---:|:---:|
| `/auth/login` | POST | Authenticate user & issue JWT | Allowed | Allowed | Allowed | Allowed |
| `/auth/refresh` | POST | Rotate refresh token | Allowed | Allowed | Allowed | Allowed |
| `/auth/me` | GET | Retrieve current user profile | Allowed | Allowed | Allowed | Allowed |
| `/auth/logout` | POST | Revoke session & token version | Allowed | Allowed | Allowed | Allowed |
| `/auth/register` | POST | Public registration (enforces `sales_rep`) | Allowed | Allowed | Allowed | Allowed |
| `/auth/users` | GET | List platform users | Allowed | Allowed | Denied (403) | Denied (403) |
| `/auth/users` | POST | Provision new user with assigned role | Allowed | Denied (403) | Denied (403) | Denied (403) |
| `/auth/users/{id}/status` | PATCH | Deactivate/activate user account | Allowed | Denied (403) | Denied (403) | Denied (403) |
| `/auth/users/{id}/role` | PATCH | Promote/demote user role | Allowed | Denied (403) | Denied (403) | Denied (403) |

---

### 2.2 Companies & Leads (`/api/v1/companies`)

| Endpoint | Method | Description | `admin` | `manager` | `sales_rep` | `analyst` |
|---|---|---|:---:|:---:|:---:|:---:|
| `/companies` | GET | List/search companies | Allowed | Allowed | Allowed | Allowed |
| `/companies/{id}` | GET | Get single company details | Allowed | Allowed | Allowed | Allowed |
| `/companies/export/csv` | GET | Export companies to CSV | Allowed | Allowed | Allowed | Allowed |
| `/companies` | POST | Create company | Allowed | Allowed | Allowed | Denied (403) |
| `/companies/{id}` | PUT | Update company | Allowed | Allowed | Owned Only | Denied (403) |
| `/companies/{id}/verify` | POST | Verify company & laptop evidence | Allowed | Allowed | Owned Only | Denied (403) |
| `/companies/{id}/sources` | POST | Attach research evidence source | Allowed | Allowed | Owned Only | Denied (403) |
| `/companies/import-csv` | POST | Batch import companies from CSV | Allowed | Allowed | Allowed | Denied (403) |

---

### 2.3 Research & Discovery (`/api/v1/research`)

| Endpoint | Method | Description | `admin` | `manager` | `sales_rep` | `analyst` |
|---|---|---|:---:|:---:|:---:|:---:|
| `/research/catalog` | GET | View discovered prospect catalog | Allowed | Allowed | Allowed | Allowed |
| `/research/discover` | POST | Trigger live discovery query | Allowed | Allowed | Allowed | Denied (403) |
| `/research/qualify/{id}` | POST | Run 7-factor qualification engine | Allowed | Allowed | Allowed | Denied (403) |

---

### 2.4 Campaigns (`/api/v1/campaigns`)

| Endpoint | Method | Description | `admin` | `manager` | `sales_rep` | `analyst` |
|---|---|---|:---:|:---:|:---:|:---:|
| `/campaigns` | GET | List campaigns | Allowed | Allowed | Allowed | Allowed |
| `/campaigns/{id}` | GET | Get campaign details | Allowed | Allowed | Allowed | Allowed |
| `/campaigns/{id}/recipients` | GET | List campaign recipients | Allowed | Allowed | Allowed | Allowed |
| `/campaigns` | POST | Create new campaign | Allowed | Allowed | Allowed | Denied (403) |
| `/campaigns/{id}` | PUT | Update campaign parameters | Allowed | Allowed | Owned Only | Denied (403) |
| `/campaigns/{id}/recipients` | POST | Add target companies to campaign | Allowed | Allowed | Owned Only | Denied (403) |
| `/campaigns/{id}/batch-draft`| POST | Batch generate AI drafts | Allowed | Allowed | Owned Only | Denied (403) |
| `/campaigns/{id}/pause` | POST | Pause active campaign | Allowed | Allowed | Denied (403) | Denied (403) |
| `/campaigns/{id}/resume` | POST | Resume paused campaign | Allowed | Allowed | Denied (403) | Denied (403) |
| `/campaigns/{id}/stop` | POST | Permanently stop campaign | Allowed | Allowed | Denied (403) | Denied (403) |
| `/campaigns/{id}/enqueue-approved` | POST | Enqueue approved drafts to outbox | Allowed | Allowed | Denied (403) | Denied (403) |
| `/campaigns/{id}/dispatch-approved` | POST | Trigger immediate dispatch | Allowed | Allowed | Denied (403) | Denied (403) |

---

### 2.5 Approval Queue & Governance (`/api/v1/approvals`)

| Endpoint | Method | Description | `admin` | `manager` | `sales_rep` | `analyst` |
|---|---|---|:---:|:---:|:---:|:---:|
| `/approvals/queue` | GET | View pending drafts queue | Allowed | Allowed | Allowed | Allowed |
| `/approvals/approve/{id}` | POST | Approve draft & bind content hash | Allowed | Allowed | Denied (403) | Denied (403) |
| `/approvals/reject/{id}` | POST | Reject draft with reason | Allowed | Allowed | Denied (403) | Denied (403) |
| `/approvals/skip/{id}` | POST | Skip draft | Allowed | Allowed | Denied (403) | Denied (403) |
| `/approvals/schedule/{id}` | POST | Set explicit dispatch schedule | Allowed | Allowed | Denied (403) | Denied (403) |
| `/approvals/regenerate/{id}` | POST | Regenerate AI draft with new tone | Allowed | Allowed | Denied (403) | Denied (403) |
| `/approvals/bulk` | POST | Bulk approve/reject/skip drafts | Allowed | Allowed | Denied (403) | Denied (403) |

---

### 2.6 Multi-Channel Outreach (`/api/v1/emails`, `/whatsapp`, `/linkedin`)

| Endpoint | Method | Description | `admin` | `manager` | `sales_rep` | `analyst` |
|---|---|---|:---:|:---:|:---:|:---:|
| `/emails/generate` | POST | Generate personalized email draft | Allowed | Allowed | Allowed | Denied (403) |
| `/emails/drafts/{id}` | GET | Get email draft content | Allowed | Allowed | Allowed | Allowed |
| `/emails/drafts/{id}` | PUT | Edit draft content | Allowed | Allowed | Owned Only | Denied (403) |
| `/whatsapp/generate` | POST | Generate WhatsApp message draft | Allowed | Allowed | Allowed | Denied (403) |
| `/whatsapp/send` | POST | Send approved WhatsApp message | Allowed | Allowed | Denied (403) | Denied (403) |
| `/whatsapp/templates` | GET | Check Meta approved templates | Allowed | Allowed | Allowed | Allowed |
| `/linkedin/drafts` | POST | Create LinkedIn outreach copy | Allowed | Allowed | Allowed | Denied (403) |
| `/linkedin/messages/{id}` | PUT | Update manual copy/send status | Allowed | Allowed | Allowed | Denied (403) |

---

### 2.7 CRM Pipeline & Follow-ups (`/api/v1/crm`)

| Endpoint | Method | Description | `admin` | `manager` | `sales_rep` | `analyst` |
|---|---|---|:---:|:---:|:---:|:---:|
| `/crm/leads` | GET | List leads across pipeline stages | Allowed | Allowed | Allowed | Allowed |
| `/crm/leads/{id}` | GET | View lead timeline & details | Allowed | Allowed | Allowed | Allowed |
| `/crm/export/csv` | GET | Export complete CRM pipeline CSV | Allowed | Allowed | Allowed | Allowed |
| `/crm/leads/{id}/status` | PATCH | Update pipeline status stage | Allowed | Allowed | Allowed | Denied (403) |
| `/crm/leads/{id}/followups`| POST | Schedule task/reminder | Allowed | Allowed | Allowed | Denied (403) |
| `/crm/leads/{id}/meetings` | POST | Log scheduled meeting | Allowed | Allowed | Allowed | Denied (403) |
| `/crm/leads/{id}/trials` | POST | Activate 90-day evaluation trial | Allowed | Allowed | Allowed | Denied (403) |
| `/crm/opt-out` | POST | Record prospect opt-out | Allowed | Allowed | Allowed | Denied (403) |

---

### 2.8 Background Jobs & Outbox (`/api/v1/jobs`)

| Endpoint | Method | Description | `admin` | `manager` | `sales_rep` | `analyst` |
|---|---|---|:---:|:---:|:---:|:---:|
| `/jobs/health` | GET | Redis, Celery & Queue health | Allowed | Allowed | Allowed | Allowed |
| `/jobs/history` | GET | Task execution log history | Allowed | Allowed | Allowed | Allowed |
| `/jobs/trigger` | POST | Trigger background task | Allowed | Allowed | Denied (403) | Denied (403) |
| `/jobs/cancel/{id}` | POST | Cancel queued background task | Allowed | Allowed | Denied (403) | Denied (403) |
| `/jobs/dlq` | GET | Inspect Dead Letter Queue | Allowed | Allowed | Denied (403) | Denied (403) |
| `/jobs/dlq/{id}/retry` | POST | Replay failed task from DLQ | Allowed | Allowed | Denied (403) | Denied (403) |
| `/jobs/outbox` | GET | Inspect transactional outbox | Allowed | Allowed | Denied (403) | Denied (403) |
| `/jobs/outbox/process` | POST | Manually flush outbox batch | Allowed | Allowed | Denied (403) | Denied (403) |

---

### 2.9 Analytics (`/api/v1/analytics`)

| Endpoint | Method | Description | `admin` | `manager` | `sales_rep` | `analyst` |
|---|---|---|:---:|:---:|:---:|:---:|
| `/analytics/dashboard` | GET | Overall funnel metrics | Allowed | Allowed | Allowed | Allowed |
| `/analytics/cities` | GET | City breakdown (Siliguri, Gangtok, etc.) | Allowed | Allowed | Allowed | Allowed |
| `/analytics/campaigns` | GET | Campaign performance comparisons | Allowed | Allowed | Allowed | Allowed |
| `/analytics/daily-digest`| GET | Daily pipeline digest | Allowed | Allowed | Allowed | Allowed |

---

### 2.10 Settings & Infrastructure (`/api/v1/settings`)

| Endpoint | Method | Description | `admin` | `manager` | `sales_rep` | `analyst` |
|---|---|---|:---:|:---:|:---:|:---:|
| `/settings` | GET | View public settings | Allowed | Allowed | Allowed | Allowed |
| `/settings/kill-switch` | GET | Check kill switch status | Allowed | Allowed | Allowed | Allowed |
| `/settings/kill-switch` | POST | Toggle emergency kill switch | Allowed | Allowed | Denied (403) | Denied (403) |
| `/settings/suppression` | GET | List suppressed identifiers | Allowed | Allowed | Denied (403) | Denied (403) |
| `/settings/audit-logs` | GET | View tamper-evident audit logs | Allowed | Allowed | Denied (403) | Denied (403) |
| `/settings/credentials` | PUT | Update integration API credentials | Allowed | Denied (403) | Denied (403) | Denied (403) |
