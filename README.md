# ActTrident AI Outreach & Sales Automation Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20TypeScript-61DAFB.svg)](https://reactjs.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%20%2F%20SQLite-336791.svg)](https://www.postgresql.org/)
[![Official Meta WhatsApp](https://img.shields.io/badge/WhatsApp-Meta%20Cloud%20API-25D366.svg)](https://developers.facebook.com/docs/whatsapp/cloud-api)

A production-grade, enterprise B2B sales outreach and automation platform purpose-built for the **[ActTrident](https://acttrident.ai/)** business development team.

The platform discovers prospective business customers across initial target cities (**Siliguri**, **Gangtok**, **Patna**, and **Bhagalpur**), conducts automated company research, identifies verified public contact information with full source attribution, evaluates managed laptop fleets (5+ devices), generates personalized multi-channel outreach presenting the proposed **90-Day Free Product Evaluation**, enforces a **Mandatory Human Approval Queue**, integrates the **Official Meta WhatsApp Business Cloud API** with strict consent verification, provides a **16-stage CRM sales pipeline**, classifies inbound replies into **10 categories**, and provides genuine campaign analytics with zero metric inflation.

---

## Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                        ActTrident Enterprise Architecture                         |
+-----------------------------------------------------------------------------------+
|  Executive Cobalt UI  : React 18 + TypeScript + Vite + Tailwind CSS               |
|  13 Modules           : Dashboard, Discovery, Leads, Research, Email, WhatsApp,   |
|                         Campaigns, Approval Queue, Inbox, CRM Pipeline, Analytics,|
|                         Integrations, Settings                                    |
|                                                                                   |
|  Backend API Engine   : Python 3.10+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2     |
|  AI Layer             : Provider-Agnostic (Gemini API, OpenAI-compatible, Mock)   |
|  Dispatch Engines     : Gmail API / Configurable SMTP & Meta WhatsApp Cloud API   |
|  Security Controls    : JWT Auth, RBAC, SSRF Guard, Prompt Injection Filter,       |
|                         Mandatory Human Approval, Immutable DB Audit Trail        |
+-----------------------------------------------------------------------------------+
```

---

## 13 Core Modules

1. **Dashboard**: Executive KPI overview, active regional campaign telemetry, and true conversion funnel.
2. **Discover Companies**: Multi-criteria search (Siliguri, Gangtok, Patna, Bhagalpur) + batch CSV import with duplicate detection and source logging.
3. **Lead Database**: Verified accounts with contact source URLs, verification timestamps, and laptop fleet evidence.
4. **AI Research**: 7-factor qualification scoring and truthful dossiers (no fabricated cyberattacks).
5. **Email Outreach**: 5 selectable tones (*Friendly professional*, *Formal*, *Technical*, *Short introductory*, *Follow-up*) presenting the proposed 90-day evaluation.
6. **WhatsApp Outreach**: Official Meta Cloud API with strict consent verification and fallback click-to-chat links.
7. **Campaigns**: Multi-channel campaigns with conservative daily limits.
8. **Approval Queue**: Mandatory human review gate (*Approve*, *Edit*, *Reject*, *Skip*, *Bulk Approve*).
9. **Inbox & Replies**: 10-category AI classifier with human sign-off for negotiations.
10. **CRM Pipeline**: 16-stage pipeline, meeting scheduler, and 90-day trial activations.
11. **Analytics**: Funnel metrics calculated with authentic denominators.
12. **Integrations**: Gemini API, OpenAI, SMTP, and Meta Cloud API connectors.
13. **Settings**: Tamper-evident audit logs and global suppression registry.

---

## Quick Start

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ & npm
- (Optional) Docker & Docker Compose

### 2. Native Local Setup

#### Backend Setup
```bash
# Install Python dependencies
pip install -r backend/requirements.txt

# Seed verified sample companies, campaigns, templates, and admin user
python backend/seed_data.py

# Run FastAPI backend
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

#### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open **[http://localhost:5173](http://localhost:5173)** in your browser.

### 3. Docker Compose Setup
```bash
docker compose up --build -d
docker compose exec backend python seed_data.py
```

---

## Default Login Credentials

| Role | Email | Password | Access Level |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@acttrident.ai` | `AdminPassword2026!` | Full platform administration |
| **Sales Specialist** | `sales@acttrident.ai` | `SalesPassword2026!` | Sales development & outreach |

---

## Automated Test Suite

Run the full suite of 21 tests:
```bash
python -m pytest
```

Test coverage includes:
- Authentication & JWT RBAC
- Company discovery & duplicate detection
- Contact-source attribution tracking
- 7-factor AI lead qualification
- SSRF prevention & prompt injection defense
- 5-tone email generation & mandatory human approval
- WhatsApp consent enforcement & template approval
- Global suppression list & opt-out enforcement
- 10-category AI reply classification
- 16-stage CRM pipeline lifecycle & 90-day evaluation trials
- Authentic conversion analytics

---

## Documentation Guides

- [User Manual](docs/USER_MANUAL.md): BD sales team workflows, lead qualification, and CRM stages.
- [Security Architecture](docs/SECURITY_DOCUMENTATION.md): SSRF defense, prompt injection shielding, RBAC, audit logging.
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md): Docker Compose, PostgreSQL configuration, production scaling.
- [Gmail & SMTP Setup Guide](docs/GMAIL_INTEGRATION_GUIDE.md): Google Workspace App Password, OAuth, SPF/DKIM/DMARC.
- [Meta WhatsApp Cloud API Guide](docs/WHATSAPP_CLOUD_API_GUIDE.md): Permanent system token, templates, webhook verification.
- [AI Provider Configuration](docs/AI_PROVIDER_CONFIGURATION.md): Gemini API, OpenAI endpoints, deterministic fallback.
- [Sample Companies CSV](sample_companies.csv): Example dataset for Siliguri, Gangtok, Patna, and Bhagalpur.
- [Sample Templates JSON](sample_templates.json): Pre-approved email and WhatsApp outreach templates.

---

## License

This project is licensed under the MIT License.
