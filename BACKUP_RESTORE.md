# ActTrident AI Sales Outreach Agent — Database Backup & Disaster Recovery Guide

## 1. Overview
ActTrident provides a unified CLI utility (`backend/scripts/backup_restore_db.py`) supporting online, consistent backups and verified restores across both SQLite (development/staging) and PostgreSQL (production).

### Key Features
- **Online Consistency:** Uses SQLite `.backup()` API or PostgreSQL `pg_dump -Fc` without stopping running services.
- **SHA-256 Manifest Generation:** Every backup writes an accompanying `.manifest.json` file with cryptographic checksum, file size, engine metadata, and creation timestamp.
- **Tamper Detection:** The restore process validates file integrity against the manifest before touching the target database, immediately aborting if checksum mismatch is detected.

---

## 2. CLI Usage Reference

### 2.1 Performing a Backup
```bash
# SQLite (Local Development)
python backend/scripts/backup_restore_db.py backup \
  --db-url "sqlite:///./acttrident.db" \
  --output "./backups/acttrident_$(date +%Y%m%d_%H%M%S).db"

# PostgreSQL (Production / Docker)
python backend/scripts/backup_restore_db.py backup \
  --db-url "$DATABASE_URL" \
  --output "./backups/acttrident_prod_$(date +%Y%m%d_%H%M%S).dump"
```

Inside Docker:
```bash
docker compose -f docker-compose.prod.yml exec backend python /app/scripts/backup_restore_db.py backup \
  --db-url "$DATABASE_URL" \
  --output "/tmp/acttrident_backup.dump"
```

### 2.2 Restoring from Backup
```bash
# SQLite (Local Development)
python backend/scripts/backup_restore_db.py restore \
  --db-url "sqlite:///./acttrident.db" \
  --input "./backups/acttrident_20261119_010000.db"

# PostgreSQL (Production / Docker)
python backend/scripts/backup_restore_db.py restore \
  --db-url "$DATABASE_URL" \
  --input "./backups/acttrident_prod_20261119_010000.dump"
```

---

## 3. Manifest Example & Tamper Verification

Each backup generates an accompanying JSON manifest:
```json
{
  "engine": "postgresql",
  "backup_file": "/app/backups/acttrident_prod.dump",
  "sha256": "8a3f81e35bfd905ad161bca1e987c0936e7a2b9e67d26bb31c6a287c881fa2f0",
  "size_bytes": 1048576,
  "created_at": "2026-11-19T01:00:00.000000+00:00"
}
```

If the file content is altered or corrupted, `restore` raises:
```text
ValueError: Backup checksum mismatch! Expected 8a3f81..., got ...
```

---

## 4. Production Backup Retention Policy

| Backup Frequency | Retention Duration | Storage Target |
| :--- | :--- | :--- |
| **Hourly Transaction Logs** | 48 hours | Local encrypted disk |
| **Daily Full Dump** | 30 days | S3 / GCS bucket with Object Lock |
| **Weekly Snapshot** | 12 weeks | Off-site encrypted archive |
| **Monthly Snapshot** | 12 months | Cold storage (compliance archive) |

### Automated Daily Cron Job Example
```bash
# Add to crontab on the Docker host:
0 2 * * * docker compose -f /opt/acttrident/docker-compose.prod.yml exec -T backend \
  python /app/scripts/backup_restore_db.py backup \
  --db-url "$DATABASE_URL" \
  --output "/app/backups/daily_$(date +\%Y\%m\%d).dump"
```

---

## 5. Disaster Recovery Runbook

1. **Assess Incident:** Identify root cause (hardware failure, data corruption, accidental drop).
2. **Halt Traffic:** Activate the Global Emergency Kill Switch or stop public container endpoints.
3. **Select Verified Backup:** Locate the latest valid backup file and confirm its `.manifest.json` matches.
4. **Provision Clean Target Database:** Ensure target PostgreSQL instance is ready and accepting connections.
5. **Execute Restore:**
   ```bash
   python backend/scripts/backup_restore_db.py restore --db-url "$TARGET_DATABASE_URL" --input "$BACKUP_FILE"
   ```
6. **Verify Migrations:**
   ```bash
   alembic -c backend/alembic.ini current
   alembic -c backend/alembic.ini upgrade head
   ```
7. **Run Sanity Check:** Verify table record counts for `companies`, `campaigns`, `email_drafts`, and `users`.
8. **Resume Outbound Dispatches:** Deactivate kill switch and resume normal operations.
