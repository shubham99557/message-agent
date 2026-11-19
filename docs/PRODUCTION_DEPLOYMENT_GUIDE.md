# ActTrident Production Deployment Guide

**Product**: ActTrident AI Outreach & Sales Automation  
**Target Environments**: Production Linux Host (Ubuntu 22.04 LTS / Debian 12 / AWS ECS / GCP GKE)  
**Container Engine**: Docker Engine 24+ & Docker Compose v2+  
**Architecture**: FastAPI ASGI + React 19 SPA + Celery + Celery Beat + Redis 7 + PostgreSQL 18

---

## 1. Production Architecture Overview

In production, ActTrident runs as a multi-container isolated stack:

```
[ Internet ] ──HTTPS (TLS 1.3)──> [ Nginx / Caddy Reverse Proxy ]
                                            │
                                            ▼ (Port 8000)
                              [ acttrident-app: FastAPI + SPA ]
                                     │               │
                    ┌────────────────┴──────┐        │
                    ▼                       ▼        ▼
       [ acttrident-postgres ]    [ acttrident-redis ]
          (PostgreSQL 18)             (Redis 7)
                                       ▲     ▲
                        ┌──────────────┘     │
                        ▼                    ▼
             [ acttrident-worker ]  [ acttrident-beat ]
                (Celery Worker)      (Periodic Cron)
```

---

## 2. Infrastructure Prerequisites

- **Host Specs**: 4 vCPU cores, 8 GB RAM, 50 GB NVMe storage.
- **Firewall Rules**:
  - Inbound: Port 80 (HTTP -> HTTPS redirect), Port 443 (HTTPS).
  - Outbound: Port 443 (HTTPS for Google/Meta APIs), Port 587 (SMTP if enabled).
  - Internal: Ports 5432 (Postgres) and 6379 (Redis) **must NOT be exposed to the public internet**.

---

## 3. Step-by-Step Deployment Procedure

### Step 1: Clone Repository & Select Implementation Branch
```bash
git clone https://github.com/shubham99557/message-agent.git /opt/acttrident
cd /opt/acttrident
git checkout feature/complete-ai-sales-agent
```

### Step 2: Configure Environment Variables
Generate high-entropy secrets and create `/opt/acttrident/.env`:
```bash
# Generate 32-character secret key
openssl rand -hex 32

# Generate Fernet encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Create `/opt/acttrident/.env` (file mode `600`):
```env
ENVIRONMENT=production
DEBUG=False
PORT=8000
HOST=0.0.0.0
CORS_ORIGINS=https://sales.acttrident.com

SECRET_KEY=your-generated-32-char-secret-key-here
ENCRYPTION_KEY=your-generated-base64-fernet-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

DATABASE_URL=postgresql://acttrident_user:ChangeMeSecurePassword2026@postgres:5432/acttrident_db
REDIS_URL=redis://:ChangeMeSecureRedisPassword2026@redis:6379/0

# External Integrations (Leave empty for safe simulated mode until provisioned)
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REFRESH_TOKEN=
GMAIL_SENDER_EMAIL=outreach@acttrident.com

META_WA_PHONE_NUMBER_ID=
META_WA_ACCESS_TOKEN=
META_WA_VERIFY_TOKEN=trident-wa-webhook-sec-99557
META_WA_APP_SECRET=
META_WABA_ID=

LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_MESSAGING_API_APPROVED=false
```

### Step 3: Run Database Migrations
Apply Alembic migrations against the database before starting the application:
```bash
docker compose -f docker-compose.prod.yml run --rm app python -m alembic -c backend/alembic.ini upgrade head
```

Verify migration status:
```bash
docker compose -f docker-compose.prod.yml run --rm app python -m alembic -c backend/alembic.ini current
# Expected: 0007_phase7_campaign_enhancements (head)
```

### Step 4: Build & Launch Production Containers
```bash
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

### Step 5: Verify Service Health & Readiness
```bash
# Check container status
docker compose -f docker-compose.prod.yml ps

# Query application health probe
curl -f http://127.0.0.1:8000/health
# Expected: {"status":"healthy","version":"1.0.0",...}

# Query readiness probe
curl -f http://127.0.0.1:8000/ready
# Expected: {"status":"ready",...}
```

---

## 4. Nginx Reverse Proxy Configuration

Create `/etc/nginx/sites-available/acttrident.conf`:
```nginx
server {
    listen 80;
    server_name sales.acttrident.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name sales.acttrident.com;

    ssl_certificate /etc/letsencrypt/live/sales.acttrident.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sales.acttrident.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: https:; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self' data:;" always;

    # Client Request Limits
    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 5. Rollback & Emergency Recovery Procedures

### Application Rollback
If a defect is detected in a new release:
1. Revert to the prior Git commit:
   ```bash
   git checkout <previous_commit_sha>
   ```
2. Re-build and restart containers:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

### Database Migration Downgrade
If a database migration must be rolled back:
```bash
docker compose -f docker-compose.prod.yml run --rm app python -m alembic -c backend/alembic.ini downgrade -1
```

### Emergency Outbound Kill Switch
If outbound communications must be immediately halted:
```bash
curl -X POST https://sales.acttrident.com/api/v1/settings/kill-switch \
     -H "Authorization: Bearer <admin_token>" \
     -H "Content-Type: application/json" \
     -d '{"active": true, "reason": "Emergency rollback halt"}'
```

---

## 6. Secret Rotation Procedure

### Rotating `SECRET_KEY` (JWT Signing):
1. Generate new 32-character key.
2. Increment `token_version` in DB for all users: `UPDATE users SET token_version = token_version + 1;` (forces re-login).
3. Update `SECRET_KEY` in `.env`.
4. Restart application container: `docker compose -f docker-compose.prod.yml restart app`.

### Rotating Integration Tokens:
1. Re-generate OAuth refresh token in Google Cloud Console or Meta Business Manager.
2. Update `.env` or submit via `PUT /api/v1/settings/credentials`.
3. The platform re-encrypts tokens with `ENCRYPTION_KEY` and reloads adapters without service downtime.
