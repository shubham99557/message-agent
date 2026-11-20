# ActTrident AI Sales Outreach & Automation Agent

A production-ready, security-hardened, multi-channel **B2B AI Sales Outreach & Automation Platform** built for **ActTrident**, targeting SMBs with 5+ managed company laptops across **Siliguri, Gangtok, Patna, and Bhagalpur** (offering the proposed **ActTrident 90-Day Free Product Evaluation**).

---

## Key Capabilities
- **Lead Discovery & Verification**: Modular permitted public discovery adapters (`Tavily`, `SerpAPI`, `OpenStreetMap`), SSRF-protected official website scanner, CSV batch import with line-level source attribution, strict RFC-2606 demo fixture quarantine, and human verification workflow (`POST /api/v1/companies/{id}/verify`).
- **Truthful AI Research & 7-Factor Qualification**: Generates concise company dossiers with explicit `missing_information`, honest `confidence_level`, zero fabricated security breaches or device counts, and transparent 7-factor heuristic scoring separating employee count from verified 5+ laptop evidence.
- **Multi-Channel Outreach (`ChannelAdapter` Architecture)**:
  - **Email**: Official Gmail OAuth 2.0 (`gmail.send` + `gmail.readonly` reply/bounce sync), SMTP fallback (`smtp_accepted`), and honest mock simulation.
  - **WhatsApp**: Official Meta Cloud API with live template sync, strictly ordered parameter validation, live opt-in consent re-check immediately prior to dispatch, and HMAC-SHA256 verified webhooks.
  - **LinkedIn**: Official LinkedIn OAuth 2.0 & compliant human-assisted handoff (zero password collection, zero cookie extraction, zero scraping) + approved Partner API support.
- **Mandatory Human Approval & Tamper-Evident Integrity**: SHA-256 content hashes, immutable `ApprovalRecord` ledger across all channels, automatic approval invalidation on edit, and atomic conditional SQL locks preventing concurrent double sends.
- **Autonomous Sales Orchestration & Safety Controls**: Global Emergency Outbound Kill Switch (**"Stop All Outbound Sending"**), campaign `pause` / `resume` / `stop` lifecycle controls, crash-safe transactional `OutboundDispatchOutbox`, Asia/Kolkata (`IST`) business-hours follow-up guard, 10-class inbound reply classification, immediate opt-out suppression, CRM pipeline, and honest analytics.
- **Enterprise Security**: DB-backed RBAC (`admin`, `manager`, `sales_rep`), short-lived JWTs + rotating refresh tokens, instant revocation via `token_version`, Fernet encryption at rest for all secrets/OAuth tokens, redacted structured JSON logging with `X-Request-ID`, and fail-fast production startup guards.

---

## Windows Local Desktop Mode (Zero Cloud Requirement)

ActTrident can be launched directly as a self-contained Windows desktop application powered by **local Ollama AI models**:

### Launching ActTrident
1. **Desktop Shortcut:** Double-click the **`ActTrident AI Sales Agent`** shortcut on your Windows Desktop.
2. **Start Menu:** Open **Start ➔ Programs ➔ ActTrident ➔ ActTrident AI Sales Agent**.
3. **Command Line:** Run `.\scripts\start_acttrident_desktop.bat`

The unified application opens at **`http://127.0.0.1:8000/`** with:
- Local AI Brain (`llama3.2:latest`, GPU-accelerated via NVIDIA CUDA at ~48 tokens/sec).
- Local persistent storage in `%LOCALAPPDATA%\ActTrident\data\acttrident.db`.
- Built-in asynchronous worker (zero mandatory Redis/Celery).
- Interactive first-run setup wizard and AI diagnostic benchmark tools.

### Stopping ActTrident
Run `.\scripts\stop_acttrident_desktop.bat` to cleanly terminate the background service.

---

## Quick Start (Local Development)

### 1. Backend (FastAPI + Alembic)
```bash
cp .env.example .env
pip install -r backend/requirements.txt
python -m alembic -c backend/alembic.ini upgrade head
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```
API docs: `http://127.0.0.1:8000/docs` • Health: `http://127.0.0.1:8000/health` • Readiness: `http://127.0.0.1:8000/ready`

### 2. Frontend (React 18 + TypeScript + Vite 6)
```bash
npm install --prefix frontend
npm run dev --prefix frontend
```
UI: `http://localhost:5173`

### 3. Production Stack (Docker Compose: PostgreSQL 16 + Redis 7 + FastAPI + Celery + Nginx)
See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for complete setup, secret generation, Alembic migration, and secure admin provisioning.

---

## Complete Documentation Index
1. [ARCHITECTURE.md](ARCHITECTURE.md) — System architecture, data model, and invariants
2. [SECURITY.md](SECURITY.md) — Authentication, RBAC, Fernet encryption, SSRF/XSS/HMAC defenses
3. [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) — Production Docker Compose deployment & hardening
4. [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) — Complete configuration reference
5. [GMAIL_INTEGRATION_GUIDE.md](GMAIL_INTEGRATION_GUIDE.md) — Official Google OAuth 2.0 Gmail setup
6. [WHATSAPP_CLOUD_API_GUIDE.md](WHATSAPP_CLOUD_API_GUIDE.md) — Official Meta WhatsApp Cloud API & webhook setup
7. [LINKEDIN_INTEGRATION_GUIDE.md](LINKEDIN_INTEGRATION_GUIDE.md) — Official LinkedIn OAuth 2.0 & compliant workflow
8. [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md) — Alembic revisions (`0001`–`0006`) & backup/restore CLI
9. [TESTING_GUIDE.md](TESTING_GUIDE.md) — Automated test suites, E2E workflow, & security penetration matrix
10. [USER_MANUAL.md](USER_MANUAL.md) — Operational guide for Sales Reps, Managers, and Admins
11. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Common errors and resolutions
