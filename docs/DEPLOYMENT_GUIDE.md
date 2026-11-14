# ActTrident AI Outreach Agent - Deployment Guide

This guide describes how to run and deploy the ActTrident platform using Docker Compose or standalone bare-metal environments.

---

## 1. Quick Start with Docker Compose

### Prerequisites
- Docker Engine 24+ & Docker Compose v2+
- Git

### Deployment Steps
1. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://github.com/acttrident/acttrident-outreach-agent.git
   cd acttrident-outreach-agent
   ```
2. Copy the sample environment file:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` to configure your secrets, SMTP password, or Meta WhatsApp tokens if deploying to production.
4. Launch the application stack:
   ```bash
   docker compose up --build -d
   ```
5. Seed initial verified company data, campaigns, and admin user:
   ```bash
   docker compose exec backend python seed_data.py
   ```
6. Access the services:
   - **Executive Cobalt Web UI**: `http://localhost:5173` or `http://localhost:80`
   - **Backend REST API**: `http://localhost:8000/api/v1`
   - **Swagger / OpenAPI Documentation**: `http://localhost:8000/docs`

---

## 2. Local Bare-Metal Development (No Docker)

### Backend (FastAPI & Python 3.10+)
```bash
# From workspace root
python -m pip install -r backend/requirements.txt
python backend/seed_data.py
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

### Frontend (React & Vite)
```bash
# In a separate terminal
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 3. Production Hardening Checklist

- [ ] Change `SECRET_KEY` in `.env` to a cryptographically random 256-bit string.
- [ ] Configure production PostgreSQL database credentials.
- [ ] Install SSL/TLS certificates via Nginx reverse proxy (Let's Encrypt / Certbot).
- [ ] Set `REQUIRE_HUMAN_APPROVAL=true` in production to enforce user review.
- [ ] Configure SPF, DKIM, and DMARC DNS records for `acttrident.ai`.
- [ ] Schedule regular automated PostgreSQL backups using `pg_dump`.
