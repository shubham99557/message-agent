# ActTrident AI Sales Outreach & Automation Agent — Production Deployment Guide

## 1. Prerequisites
- Docker Engine 24+ and Docker Compose v2+
- PostgreSQL 16 (included in Docker Compose or managed cloud PostgreSQL)
- Redis 7 (included in Docker Compose for Celery workers and Beat scheduler)
- Reverse proxy with TLS (Nginx, Caddy, or Cloud Load Balancer) terminating HTTPS for your public domain
- Verified DNS records with SPF, DKIM, and DMARC for outbound email sender domains

---

## 2. Multi-Environment Docker Orchestration

The application provides dedicated Docker Compose configurations tailored for each deployment stage:

| Environment | Compose File | Command | Characteristics |
| :--- | :--- | :--- | :--- |
| **Development** | `docker-compose.dev.yml` | `docker compose -f docker-compose.dev.yml up` | Live source bind-mounts, uvicorn `--reload`, exposed local DB/Redis ports. |
| **Staging** | `docker-compose.staging.yml` | `docker compose -f docker-compose.staging.yml up -d` | Automated migration pre-flight, sandbox integration testing, controlled logs. |
| **Production** | `docker-compose.prod.yml` | `docker compose -f docker-compose.prod.yml up -d` | Hardened networks, log rotation (`20m`/`5 files`), strict secret validation. |

---

## 3. Prepare Environment Secrets

1. Copy `.env.example` to `.env` (or `.env.production`):
   ```bash
   cp .env.example .env
   ```
2. Generate strong, cryptographically secure secrets:
   ```bash
   python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"
   python -c "from cryptography.fernet import Fernet; print('CREDENTIAL_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
   ```
3. Configure mandatory production parameters in `.env`:
   - `ENVIRONMENT=production`
   - `POSTGRES_USER=acttrident`
   - `POSTGRES_PASSWORD=<strong-random-db-password>`
   - `POSTGRES_DB=acttrident_db`
   - `SECRET_KEY=<generated-48-byte-key>`
   - `CREDENTIAL_ENCRYPTION_KEY=<generated-fernet-key>`
   - `BACKEND_CORS_ORIGINS=https://outreach.your-domain.com` (wildcard `*` strictly blocked)
   - `TIMEZONE=Asia/Kolkata`
   - Provider credentials as needed (see [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md), [GMAIL_SETUP.md](GMAIL_SETUP.md), [WHATSAPP_SETUP.md](WHATSAPP_SETUP.md)).

---

## 4. Production Deployment Sequence

```bash
# 1. Start core data stores
docker compose -f docker-compose.prod.yml up -d postgres redis

# 2. Build application containers
docker compose -f docker-compose.prod.yml build backend celery_worker celery_beat frontend

# 3. Apply Alembic database migrations up to head (0007_phase7_campaign_enhancements)
docker compose -f docker-compose.prod.yml run --rm backend python -m alembic -c /app/alembic.ini upgrade head

# 4. Provision initial administrator account (interactively, zero hardcoded passwords)
docker compose -f docker-compose.prod.yml run --rm backend python /app/scripts/provision_admin.py \
  --email admin@acttrident.ai \
  --name "ActTrident Admin"

# 5. Start full production stack
docker compose -f docker-compose.prod.yml up -d
```

---

## 5. Health, Readiness & Verification Probes

```bash
# Liveness probe (HTTP 200 OK)
curl -f http://localhost:8000/health

# Readiness probe (verifies live PostgreSQL connectivity)
curl -f http://localhost:8000/ready

# Verify current Alembic migration revision
docker compose -f docker-compose.prod.yml exec backend python -m alembic -c /app/alembic.ini current

# Inspect running Celery worker queues and tasks
docker compose -f docker-compose.prod.yml exec celery_worker celery -A app.worker.celery_app.celery_app inspect ping
```

---

## 6. Reverse Proxy & TLS Configuration

Place Nginx or Caddy in front of the public container endpoints:

```nginx
# Example Nginx TLS Reverse Proxy
server {
    listen 443 ssl http2;
    server_name outreach.acttrident.ai;

    ssl_certificate /etc/letsencrypt/live/outreach.acttrident.ai/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/outreach.acttrident.ai/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Frontend UI
    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    # Backend API & Webhooks
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

---

## 7. Email Sender Domain Authentication (DNS)

To prevent delivery failures and preserve sender reputation:
1. **SPF Record:**
   ```text
   v=spf1 include:_spf.google.com ~all
   ```
2. **DKIM Record:**
   Publish the 2048-bit Google Workspace DKIM TXT record at `google._domainkey.your-domain.com`.
3. **DMARC Record:**
   ```text
   v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@your-domain.com; pct=100
   ```

---

## 8. Backup, Rollback & Incident Response

- **Automated Backup:**
  ```bash
  docker compose -f docker-compose.prod.yml exec backend python /app/scripts/backup_restore_db.py backup \
    --db-url "$DATABASE_URL" \
    --output "/tmp/pre_deploy_$(date +%Y%m%d_%H%M%S).dump"
  ```
- **Emergency Outbound Kill Switch:**
  To halt all outbound dispatches immediately without taking the UI offline:
  Navigate to **Settings** → **Global Emergency Kill Switch** → Toggle **ON**, or execute:
  ```bash
  curl -X POST http://localhost:8000/api/v1/settings/kill-switch \
    -H "Authorization: Bearer <ADMIN_TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{"active": true, "reason": "Operator-initiated emergency freeze"}'
  ```
- **Migration Rollback:**
  ```bash
  docker compose -f docker-compose.prod.yml exec backend python -m alembic -c /app/alembic.ini downgrade -1
  ```
