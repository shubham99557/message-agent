# ActTrident AI Sales Outreach Agent — Database Migrations & Backup Guide

## 1. Overview
Production schema changes are managed exclusively through **Alembic** (`backend/alembic.ini` and `backend/alembic/versions/`).  
Automatic table creation (`sync_missing_columns`) is strictly disabled in `ENVIRONMENT=production`.

---

## 2. Mandatory Backup Procedure (Run Before Every Migration)

### PostgreSQL (Production / Staging)
```bash
# 1. Create a timestamped compressed backup before migrating
pg_dump -Fc --no-owner --dbname="$DATABASE_URL" -f "backup_pre_migration_$(date +%Y%m%d_%H%M%S).dump"

# 2. Verify backup archive integrity
pg_restore --list backup_pre_migration_*.dump | head -n 20
```

### SQLite (Local Development Only)
```bash
cp acttrident.db "acttrident_backup_$(date +%Y%m%d_%H%M%S).db"
```

---

## 3. Running Migrations

```bash
# Inspect current revision and migration history
python -m alembic -c backend/alembic.ini current
python -m alembic -c backend/alembic.ini history --verbose

# Apply all pending migrations safely
python -m alembic -c backend/alembic.ini upgrade head
```

---

## 4. Authoring New Migrations

```bash
# Auto-generate a new revision after modifying ORM models in backend/app/models/
python -m alembic -c backend/alembic.ini revision --autogenerate -m "describe_change"

# Always review the generated file in backend/alembic/versions/ before applying!
```

---

## 5. Rollback & Recovery Procedures

### Step-Down One Revision
```bash
python -m alembic -c backend/alembic.ini downgrade -1
```

### Full Database Restore (Emergency Recovery)
```bash
# PostgreSQL restore from pre-migration dump
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" backup_pre_migration_YYYYMMDD_HHMMSS.dump

# SQLite local restore
cp acttrident_backup_YYYYMMDD_HHMMSS.db acttrident.db
```

---

## 6. Revision Log

| Revision ID | Phase | Description |
| :--- | :---: | :--- |
| `0001_phase1_foundation` | Phase 1 | Baseline schema verification, `users.token_version` for immediate JWT revocation, `approval_records` immutable ledger, and non-destructive upgrade support for existing databases. |
| `0002_phase2_email_connections` | Phase 2 | Adds `channel_connections` (Fernet-encrypted OAuth tokens & status), `email_send_attempts` (send attempt ledger separate from delivery outcomes), `email_drafts.provider_thread_id`/`idempotency_key`, and `replies.provider_message_id`/`provider_thread_id`/`campaign_id`. |
