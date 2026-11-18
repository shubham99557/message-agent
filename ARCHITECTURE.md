# ActTrident AI Sales Outreach & Automation Agent — System Architecture

## 1. High-Level Layered Architecture

ActTrident is structured as a modular, multi-channel B2B sales outreach platform targeting SMBs with 5+ managed company laptops across Siliguri, Gangtok, Patna, and Bhagalpur (offering the proposed ActTrident 90-Day Free Product Evaluation).

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Frontend (React 18 + TypeScript + Vite 6 + Tailwind Executive Cobalt UI)   │
│ 14 Views: Dashboard, Discovery, Leads, Research, Email, WhatsApp,          │
│           LinkedIn, Campaigns, Approvals, Inbox, CRM, Analytics,           │
│           Integrations, Settings (Kill Switch & RBAC)                      │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │ HTTPS / REST (/api/v1/*) + JWT Auth
┌──────────────────────────────────▼─────────────────────────────────────────┐
│ API Layer (FastAPI + Pydantic v2 + Request Correlation + RBAC Deps)        │
│ auth, companies, discovery, qualification, research, emails, approvals,    │
│ campaigns, whatsapp, linkedin, replies, crm, analytics, settings, jobs,    │
│ integrations                                                               │
└───────────────┬───────────────────────────────┬────────────────────────────┘
                │                               │
┌───────────────▼────────────────┐ ┌────────────▼────────────────────────────┐
│ Service & Orchestration Layer  │ │ Unified Integration Adapter Layer       │
│ - discovery_service            │ │ - ChannelAdapter ABC                    │
│ - research_service             │ │   ├── EmailChannelAdapter (Gmail/SMTP)  │
│ - qualification_service        │ │   ├── WhatsAppChannelAdapter (Meta API) │
│ - email_generator / sender     │ │   └── LinkedInChannelAdapter (OAuth2)   │
│ - whatsapp_service             │ │ - DiscoverySourceAdapter ABC            │
│ - linkedin_service             │ │   ├── TavilyDiscoveryAdapter            │
│ - reply_classifier_service     │ │   ├── SerpApiDiscoveryAdapter           │
│ - followup_service (IST guard) │ │   └── OpenStreetMapPublicAdapter        │
│ - orchestration_service        │ └─────────────────────────────────────────┘
│   (Kill Switch, Outbox, Pause) │
└───────────────┬────────────────┘
                │
┌───────────────▼────────────────┐ ┌─────────────────────────────────────────┐
│ Primary Database (Alembic 0006)│ │ Async Worker Engine (Optional in Dev)   │
│ - PostgreSQL 16 (Production)   │ │ - Redis 7 Broker & Result Backend       │
│ - SQLite (Local Dev/Test Only) │ │ - Celery Workers + Beat (Asia/Kolkata)  │
└────────────────────────────────┘ └─────────────────────────────────────────┘
```

---

## 2. Core Data Model (Managed Exclusively via Alembic Revisions `0001`–`0006`)
- **Identity & Access**: `users` (with `token_version` for immediate JWT revocation), `refresh_tokens` (SHA-256 hashed, rotated, revocable), `audit_logs`.
- **Prospect Intelligence**: `companies` (`is_demo`, `verification_status`, `verification_method`, separate `employee_count_*` and `laptop_count_verified`), `company_contacts`, `contact_sources`, `research_reports` (`missing_information`, `confidence_level`).
- **Outreach & Mandatory Approvals**: `campaigns`, `campaign_recipients`, `email_drafts`, `email_send_attempts`, `email_events`, `whatsapp_templates`, `whatsapp_messages`, `contact_consents`, `linkedin_messages`, `approval_records` (immutable ledger across Email, WhatsApp, LinkedIn).
- **Inbound & CRM**: `conversations`, `replies` (10-class classification + `provider_message_id` dedupe), `leads`, `meetings`, `followups`, `trials`, `customers`, `suppression_list`.
- **Integrations & Orchestration**: `channel_connections` (Fernet-encrypted OAuth tokens), `integration_credentials` (Fernet-encrypted API keys), `system_settings` (Global Emergency Kill Switch), `outbound_dispatch_outbox` (crash-safe transactional outbox), `background_task_records`, `dead_letter_tasks`, `webhook_events`.

---

## 3. Non-Negotiable Architectural Invariants
1. **Mandatory Human Approval**: No Email, WhatsApp, LinkedIn, or follow-up message can be dispatched without explicit `admin`/`manager` approval backed by a SHA-256 `content_hash` and an immutable `ApprovalRecord`. Editing an approved draft immediately invalidates approval.
2. **Truthful Delivery Reporting**: Simulation mode never fabricates provider message IDs (`provider_message_id=None`, `meta_message_id=None`). SMTP acceptance is recorded as `smtp_accepted`, never falsely as `delivered`.
3. **Demo Quarantine**: RFC-2606 `.example.com`/`.test` domains are auto-quarantined as `is_demo=True, verification_status="demo_fixture"`, blocked from verification, and never returned in `ENVIRONMENT=production`.
4. **Global Emergency Kill Switch**: Persisted in `system_settings` and enforced across Email, WhatsApp, LinkedIn, Campaigns, Outbox, and Follow-ups.
