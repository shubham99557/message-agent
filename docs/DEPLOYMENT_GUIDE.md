# ActTrident Deployment Guide: Staging & Production

**Architecture**: Multi-Tier Containerized Service  
**Container Engine**: Docker 24+ & Docker Compose v2+  
**Target Environments**: Local Development, Staging, Production (Ubuntu 22.04 LTS / Debian 12 / AWS ECS / GCP GKE)

---

## 1. System Requirements

### Hardware Sizing (Production):
- **CPU**: 4 vCPU cores (minimum 2 vCPU for staging).
- **RAM**: 8 GB RAM (minimum 4 GB for staging).
- **Storage**: 50 GB NVMe / SSD with daily snapshots.

### Software Dependencies:
- **Docker Engine**: Version 24.0+
- **Docker Compose**: Version 2.20+
- **PostgreSQL**: Version 18.x
- **Redis**: Version 7.x
- **Node.js**: Version 20.x LTS (for frontend builds)
- **Python**: Version 3.12 or 3.14

---

## 2. Multi-Environment Docker Architecture

ActTrident provides dedicated Compose profiles for each operational stage:

```
├── Dockerfile                   # Multi-stage container (Node Vite build + Python FastAPI)
├── docker-compose.dev.yml       # Local dev with hot-reloading & SQLite/local Redis
├── docker-compose.staging.yml   # Staging with PostgreSQL, Redis, Celery & Beat
├── docker-compose.prod.yml      # Hardened production with replicas, TLS & resource limits
└── docker-compose.yml           # Base orchestration file
```

---

## 3. Production Deployment Procedure

### Step 1: Clone Repository & Select Implementation Branch
```bash
git clone https://github.com/shubham99557/message-agent.git
cd message-agent
git checkout feature/complete-ai-sales-agent
```

### Step 2: Configure Production Environment Variables
Create a hardened `.env` file in the project root:
```bash
cp .env.example .env
chmod 600 .env
```

Populate the required production keys (see `docs/ENVIRONMENT_VARIABLES.md` for full reference):
```env
ENVIRONMENT=production
SECRET_KEY=generate-with-openssl-rand-hex-32-character-entropy-minimum
ENCRYPTION_KEY=generate-with-python-fernet-generate-key
DATABASE_URL=postgresql://acttrident_user:StrongDbPassword2026@postgres:5432/acttrident_db
REDIS_URL=redis://:StrongRedisPassword2026@redis:6379/0
CORS_ORIGINS=https://sales.acttrident.com

# Service Credentials
GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your-gcp-client-secret
GMAIL_REFRESH_TOKEN=your-gmail-refresh-token
GMAIL_SENDER_EMAIL=outreach@acttrident.com

META_WA_PHONE_NUMBER_ID=your-wa-phone-number-id
META_WA_ACCESS_TOKEN=your-meta-system-user-token
META_WA_VERIFY_TOKEN=your-wa-verify-secret
META_WA_APP_SECRET=your-meta-app-secret
META_WABA_ID=your-waba-account-id
```

### Step 3: Execute Database Migrations
Apply the complete Alembic schema migrations:
```bash
python -m alembic -c backend/alembic.ini upgrade head
```
Verify the migration status:
```bash
python -m alembic -c backend/alembic.ini current
# Expected: 0007_phase7_campaign_enhancements (head)
```

### Step 4: Build & Launch Production Containers
Build the multi-stage Docker image and start all background services:
```bash
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

### Step 5: Verify Container Health
```bash
docker compose -f docker-compose.prod.yml ps
```
All containers (`app`, `postgres`, `redis`, `celery_worker`, `celery_beat`) should report `Up (healthy)`.

Inspect API readiness:
```bash
curl -f https://sales.acttrident.com/api/v1/jobs/health
```

---

## 4. Production Hardening Checklist

- [x] **Non-Root Execution**: The Docker container runs under an unprivileged `appuser` (UID 10001).
- [x] **Database Isolation**: PostgreSQL binds strictly to the internal Docker network; no public port exposure.
- [x] **Redis Password Authentication**: Redis requires strict `requirepass` authentication.
- [x] **TLS Termination**: An Nginx or Caddy reverse proxy terminates TLS 1.3 in front of the Uvicorn container, enforcing HSTS headers.
- [x] **CORS Whitelist**: `CORS_ORIGINS` is restricted strictly to your production domain (e.g. `https://sales.acttrident.com`).
- [x] **Static Asset Caching**: Frontend static bundles (`/app/frontend/dist/assets/*`) are served with immutable cache-control headers (`max-age=31536000, immutable`).
- [x] **Process Supervision**: Docker Compose restart policy is configured to `unless-stopped` with health checks every 30 seconds.
