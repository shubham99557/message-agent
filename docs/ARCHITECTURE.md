# ActTrident Architecture Specification

**Product**: ActTrident AI Outreach & Sales Automation  
**Audience**: Software Architects, Lead Engineers, DevOps, System Administrators  
**Revision**: 2.0 (Production Release)

---

## 1. System Overview

ActTrident is an enterprise-grade AI-powered sales outreach platform tailored for business discovery, qualification, and multi-channel engagement in Tier 2 and Tier 3 Indian technology hubs (Siliguri, Gangtok, Patna, Bhagalpur). The platform automates lead identification, enforces strict device-evidence qualification (5+ company-managed laptops), drafts hyper-personalized outreach, and requires human-in-the-loop governance prior to multi-channel delivery.

---

## 2. High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph Client Tier
        UI["React 19 / TypeScript SPA<br/>(Vite, Tailwind, Lucide)"]
    end

    subgraph Application Tier
        API["FastAPI Application Server<br/>(Uvicorn ASGI, Python 3.12/3.14)"]
        AUTH["RBAC & Security Engine<br/>(JWT tv, Fernet, Passlib)"]
        POLICY["Compliance & Truthfulness Engine<br/>(Opt-out, 5+ Laptop Heuristic)"]
        ORCH["Campaign & Outbox Orchestrator"]
    end

    subgraph Background Execution Tier
        REDIS["Redis 7 Broker & Cache"]
        WORKER["Celery Asynchronous Workers"]
        BEAT["Celery Beat Periodic Scheduler"]
    end

    subgraph Data Tier
        DB[("PostgreSQL 18 Primary Database<br/>(SQLAlchemy ORM + Alembic)")]
        AUDIT[("Tamper-Evident Audit Logs")]
    end

    subgraph External Providers
        GMAIL["Google Workspace / Gmail API v1"]
        META["Meta WhatsApp Cloud API v19.0"]
        LINKEDIN["LinkedIn OAuth 2.0 API"]
        DISC["Tavily / SerpApi Web Scrapers"]
    end

    UI -->|REST API over TLS / Bearer JWT| API
    API --> AUTH
    API --> POLICY
    API --> ORCH
    API --> DB
    API --> AUDIT
    ORCH -->|Enqueue Task / Outbox Item| REDIS

    BEAT -->|Cron Triggers| REDIS
    REDIS --> WORKER
    WORKER --> DB
    WORKER --> ORCH

    WORKER -->|Send / Sync| GMAIL
    WORKER -->|Send / Webhook| META
    WORKER -->|Profile Sync / Handoff| LINKEDIN
    WORKER -->|Search & Enrich| DISC
```

---

## 3. Component Breakdown

### 3.1 Frontend Single Page Application (SPA)
- **Framework**: React 19, TypeScript, Vite.
- **Styling**: Tailwind CSS with custom ActTrident dark-mode cobalt palette (`#0f172a`, `#1e293b`, `#3b82f6`).
- **State & Data Fetching**: Centralized `api` client (`frontend/src/api/client.ts`) with automatic 401 JWT refresh token rotation, request queuing during refresh, and badge polling.
- **Key Modules**:
  1. `DashboardView`: Real-time funnel metrics, city breakdown, conversion rates.
  2. `DiscoveryView`: Targeted query generation across Siliguri, Gangtok, Patna, and Bhagalpur.
  3. `LeadsView`: Company directory with verified laptop counts and MCA/LinkedIn evidence sources.
  4. `ResearchView`: Deep company profiling and 7-factor qualification scoring.
  5. `CampaignsView`: Multi-channel campaign builder with lifecycle controls (Start, Pause, Stop).
  6. `ApprovalQueueView`: Human-in-the-loop review queue (Approve, Reject, Skip, Regenerate, Schedule).
  7. `EmailOutreachView`: Email draft composer with AI personalization and tone controls.
  8. `WhatsAppView`: WhatsApp message manager with template status and opt-in badges.
  9. `LinkedInView`: Manual handoff assistant and copy-paste clipboard workflow.
  10. `InboxView`: Inbound reply classification and sentiment categorization.
  11. `CrmPipelineView`: Visual 7-stage sales pipeline with streaming CSV export.
  12. `SettingsView`: Emergency kill switch, RBAC user provisioning, and suppression registry.

### 3.2 Backend Application Server
- **Framework**: FastAPI (Python ASGI) structured with clean architectural boundaries:
  - `app/api/endpoints/`: Thin controllers exposing versioned REST endpoints (`/api/v1/*`).
  - `app/services/`: Core business logic, qualification rules, and campaign workflows.
  - `app/models/`: Declarative SQLAlchemy models.
  - `app/schemas/`: Pydantic V2 request/response validation schemas.
  - `app/integrations/`: Channel adapters implementing standardized provider interfaces.
  - `app/core/`: Security, cryptographic operations, database session management, and configuration.

### 3.3 Background Worker & Task Queue
- **Broker**: Redis 7 on `redis://localhost:6379/0`.
- **Worker**: Celery process running `app.core.celery_app.celery_app`.
- **Beat Scheduler**: Manages periodic background jobs:
  - `process-transactional-outbox`: Every 60 seconds (flushes ready outbox items).
  - `sync-gmail-inbox-replies`: Every 300 seconds (polls Gmail for replies and bounces).
  - `nightly-lead-discovery`: Daily at 02:00 UTC (automated enrichment for target cities).
  - `process-scheduled-followups`: Every 600 seconds (checks due CRM reminders).
- **Dead Letter Queue (DLQ)**: Tasks exhausting max retries (3) are persisted to `DeadLetterTask` for operator inspection.

### 3.4 Data Layer
- **Primary Database**: PostgreSQL 18 in production, SQLite in local unit tests.
- **Migration Framework**: Alembic managing reversible migrations. Current head: `0007_phase7_campaign_enhancements`.
- **Integrity Constraints**: Foreign key cascading, unique constraints on user emails, company domains, outbox idempotency keys, and token hashes.

---

## 4. End-to-End Operational Flows

### 4.1 Discovery & Truthful Qualification Flow
```mermaid
sequenceDiagram
    autonumber
    actor Operator as Sales Operator
    participant API as FastAPI Backend
    participant Disc as Discovery Service
    participant Qual as Qualification Engine
    participant DB as PostgreSQL

    Operator->>API: POST /api/v1/research/discover (City, Industry)
    API->>Disc: search_companies_in_catalog()
    Disc->>Disc: Filter synthetic demo domains (.example.com)
    Disc->>DB: Store raw prospect records
    API->>Qual: qualify_company()
    Note over Qual: Evaluates 7 Factors (25% weight on 5+ verified laptops)
    Qual->>DB: Store qualification_score & evidence_source
    API-->>Operator: Return Discovered & Qualified Companies
```

### 4.2 Human-in-the-Loop Approval & Outbox Dispatch Flow
```mermaid
sequenceDiagram
    autonumber
    actor Mgr as Campaign Manager
    participant Appr as Approval Controller
    participant DB as PostgreSQL
    participant Outbox as Outbound Dispatch Outbox
    participant Worker as Celery Worker
    participant Provider as Gmail / Meta API

    Mgr->>Appr: POST /api/v1/approvals/approve/{draft_id}
    Note over Appr: Computes SHA256 content hash of subject + body
    Appr->>DB: Set approval_status = "approved", record content_hash
    Appr->>Outbox: enqueue_outbox_dispatch()
    Note over Outbox: Generates unique idempotency_key
    Mgr->>Appr: POST /api/v1/campaigns/{id}/enqueue-approved
    Outbox->>DB: Status = "pending", scheduled_at = now()

    loop Every 60 Seconds (Celery Beat)
        Worker->>Outbox: Claim pending outbox items (SELECT FOR UPDATE)
        Worker->>Worker: Check Global Kill Switch
        Worker->>Worker: Verify Rate Limits (Burst & Daily)
        alt Kill Switch Active or Rate Limit Exceeded
            Worker->>Outbox: Revert to pending / backoff
        else Send Allowed
            Worker->>Provider: Dispatch external API call
            Provider-->>Worker: Return message_id (e.g. wamid / Gmail ID)
            Worker->>DB: Update outbox status = "sent", record provider_message_id
        end
    end
```

---

## 5. Reliability & Delivery Guarantees

1. **Exactly-Once Semantics**: The combination of `OutboundDispatchOutbox`, database transaction isolation, and SHA256 content hashes guarantees that network timeouts or worker crashes will not produce duplicate customer outreach.
2. **Safe Fallback**: In development or staging without live credentials, adapters automatically operate in `simulated` mode, recording mock receipts without making network requests.
3. **Suppression Enforcement**: The `handle_opt_out` routine immediately suppresses email, phone, or WhatsApp identifiers across all active campaigns and future discovery cycles.
