# ActTrident AI Sales Outreach & Automation Agent — Production Deployment Guide

## 1. Prerequisites
- Docker Engine 24+ and Docker Compose v2+
- PostgreSQL 16 (included in `docker-compose.yml` or managed cloud PostgreSQL)
- Redis 7 (included in `docker-compose.yml` for Celery workers and Beat scheduler)
- Reverse proxy with TLS (Nginx, Caddy, or Cloud Load Balancer) terminating HTTPS for your public domain

---

## 2. Prepare Production Environment File
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Generate strong unique production secrets:
   ```bash
   python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"
   python -c "from cryptography.fernet import Fernet; print('CREDENTIAL_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
   ```
3. Configure mandatory production settings in `.env`:
   - `ENVIRONMENT=production`
   - `POSTGRES_PASSWORD=<strong-random-password>`
   - `SECRET_KEY=<generated-48-byte-key>`
   - `CREDENTIAL_ENCRYPTION_KEY=<generated-fernet-key>`
   - `BACKEND_CORS_ORIGINS=https://outreach.your-domain.com` (never `*`)
   - `TIMEZONE=Asia/Kolkata`
   - Provider credentials as needed (see [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md), [GMAIL_INTEGRATION_GUIDE.md](GMAIL_INTEGRATION_GUIDE.md), [WHATSAPP_CLOUD_API_GUIDE.md](WHATSAPP_CLOUD_API_GUIDE.md), [LINKEDIN_INTEGRATION_GUIDE.md](LINKEDIN_INTEGRATION_GUIDE.md)).

---

## 3. Build, Migrate & Provision Admin
```bash
# 1. Start PostgreSQL and Redis first
docker compose up -d postgres redis

# 2. Build application containers
docker compose build backend celery_worker celery_beat frontend

# 3. Apply Alembic database migrations to head (0006_phase6_orchestration_outbox)
docker compose run --rm backend python -m alembic -c /app/backend/alembic.ini upgrade head

# 4. Provision the initial production admin user interactively (never hardcoded!)
docker compose run --rm backend python /app/backend/scripts/provision_admin.py \
  --email admin@your-domain.com \
  --name "ActTrident Admin"

# 5. Start full production stack
docker compose up -d
```

---

## 4. Health & Readiness Verification
```bash
# Liveness probe
curl -f http://localhost:8000/health

# Readiness probe (verifies live PostgreSQL connectivity)
curl -f http://localhost:8000/ready

# Verify Alembic head revision
docker compose exec backend python -m alembic -c /app/backend/alembic.ini current
```

---

## 5. Backups & Rollback
- Always run a pre-deployment backup before upgrading migrations:
  ```bash
  python backend/scripts/backup_restore_db.py backup \
    --db-url "$DATABASE_URL" \
    --output "./backups/pre_deploy_$(date +%Y%m%d_%H%M%S).dump"
  ```
- Emergency outbound stop: Activate the **Global Emergency Outbound Kill Switch** in **Settings** (or `POST /api/v1/settings/kill-switch` with `{"active": true}`) to halt all outbound traffic instantaneously without taking the UI offline.
- Detailed migration rollback steps: see [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md).
