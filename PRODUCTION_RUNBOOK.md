# ACTTRIDENT AI OUTREACH AGENT — PRODUCTION RUNBOOK

**Target Branch:** `feature/autonomous-automation`  
**Deployment Tooling:** Docker Compose, PostgreSQL 16, Redis 7, Celery 5.4, FastAPI, React  
**Default Timezone:** `Asia/Kolkata` (IST)  

---

## 1. Quick Start with Docker Compose

To deploy the entire production stack in isolated containers:

```bash
# 1. Clone repository and switch to the autonomous feature branch
git clone https://github.com/shubham99557/message-agent.git
cd message-agent
git checkout feature/autonomous-automation

# 2. Copy and configure production secrets
cp .env.example .env
# Edit .env with strong production credentials (see CREDENTIALS.md)

# 3. Build and launch all containerized services
docker compose up -d --build

# 4. Verify healthy service containers
docker compose ps
```

The stack launches 5 isolated services:
1. `acttrident_postgres`: Persistent relational database (internal network).
2. `acttrident_redis`: Background task message broker and sliding-window rate limiter (internal network).
3. `acttrident_backend`: FastAPI core application engine on port `8000`.
4. `acttrident_celery_worker`: 4-concurrency distributed worker consuming `research`, `outreach`, `high_priority`, and `default` queues.
5. `acttrident_celery_beat`: Periodic cron scheduler aligned to `Asia/Kolkata`.
6. `acttrident_frontend`: Nginx reverse proxy serving the React 18 production build on port `80`.

---

## 2. Local Development Execution

### Backend & API Server:
```bash
# Navigate to backend and install dependencies
cd backend
python -m pip install -r requirements.txt

# Run database migrations / initialization
python -m app.main

# Launch FastAPI development server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Celery Worker & Scheduler:
```bash
# In a separate terminal session
celery -A app.worker.celery_app.celery_app worker --loglevel=info -Q research,outreach,high_priority,default -c 4

# In another terminal session (Beat Scheduler)
celery -A app.worker.celery_app.celery_app beat --loglevel=info
```

### Frontend UI:
```bash
cd frontend
npm install
npm run dev
# Accessible on http://localhost:5173
```

---

## 3. Worker Health & Queue Monitoring

### Check Background Engine Health via REST API:
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/health" \
  -H "Authorization: Bearer <ADMIN_OR_MANAGER_JWT_TOKEN>"
```

### Inspect Dead-Letter Queue (DLQ):
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/dead-letter" \
  -H "Authorization: Bearer <ADMIN_OR_MANAGER_JWT_TOKEN>"
```

### Requeue Failed Dead-Letter Task:
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/dead-letter/<DLQ_ID>/retry" \
  -H "Authorization: Bearer <ADMIN_OR_MANAGER_JWT_TOKEN>"
```

---

## 4. Disaster Recovery & Rollback Procedures

1. **Broker Failure (Redis Outage):**
   - The job engine automatically falls back to synchronous in-process task execution.
   - Restart Redis container: `docker compose restart redis`.
   - Celery workers will automatically reconnect with exponential backoff.

2. **Poison Pill Task Recovery:**
   - Any task failing after 3 consecutive retries is permanently moved to `dead_letter_tasks`.
   - The primary pipeline continues unimpeded.
   - Inspect the `final_error` field on the DLQ record before triggering `/retry`.

3. **Database Backup & Restore:**
   ```bash
   # Create backup
   docker exec -t acttrident_postgres pg_dump -U acttrident acttrident_db > backup_$(date +%F).sql

   # Restore backup
   cat backup_2026-11-15.sql | docker exec -i acttrident_postgres psql -U acttrident -d acttrident_db
   ```
