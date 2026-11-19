# Database Backup, Disaster Recovery & PITR Guide

**Database**: PostgreSQL 18.x  
**Backup Utilities**: `pg_dump`, `pg_restore`, `gpg`, `aws-cli`  
**Target RPO**: <= 1 hour | **Target RTO**: <= 30 minutes

---

## 1. Backup Strategy & Retention Schedule

ActTrident data includes prospect intelligence, fleet evidence, immutable approval records, and global suppression lists. The backup policy enforces:

| Frequency | Retention | Storage Location | Encryption |
|---|---|---|---|
| **Daily Full Dump** (01:00 UTC) | 30 Days | Local SSD + S3 Standard | AES-256 via GPG |
| **Weekly Snapshot** (Sundays) | 12 Weeks | Offsite Air-gapped Bucket | AES-256 via GPG + AWS KMS |
| **Monthly Archive** (1st of month) | 12 Months | Glacier / Deep Archive | AES-256 via GPG |
| **Write-Ahead Logs (WAL)** | 7 Days | Continuous Archiving Bucket | AWS KMS SSE |

---

## 2. Automated Backup Script (`/usr/local/bin/backup_acttrident.sh`)

Deploy the following production backup script:

```bash
#!/usr/bin/env bash
set -eo pipefail

BACKUP_DIR="/var/backups/acttrident"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DUMP_FILE="${BACKUP_DIR}/acttrident_db_${TIMESTAMP}.dump"
GPG_RECIPIENT="security@acttrident.com"
S3_BUCKET="s3://acttrident-backups-prod/database"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting ActTrident PostgreSQL backup..."

# Execute binary custom-format pg_dump
docker exec -t acttrident-postgres pg_dump \
    -U acttrident_user \
    -d acttrident_db \
    -F c \
    -b -v \
    -f "/tmp/backup.dump"

# Copy dump from container to host
docker cp acttrident-postgres:/tmp/backup.dump "${DUMP_FILE}"
docker exec -t acttrident-postgres rm -f /tmp/backup.dump

echo "[$(date)] Backup completed: ${DUMP_FILE} ($(du -h ${DUMP_FILE} | cut -f1))"

# Encrypt backup with GPG
gpg --yes --batch --encrypt --recipient "${GPG_RECIPIENT}" "${DUMP_FILE}"
rm -f "${DUMP_FILE}"
ENCRYPTED_FILE="${DUMP_FILE}.gpg"

# Upload to offsite cloud storage
aws s3 cp "${ENCRYPTED_FILE}" "${S3_BUCKET}/$(date +%Y)/$(date +%m)/" --sse aws:kms

# Prune local backups older than 30 days
find "${BACKUP_DIR}" -type f -name "*.dump.gpg" -mtime +30 -delete

echo "[$(date)] Backup and sync lifecycle completed successfully."
```

Configure root crontab:
```bash
0 1 * * * /usr/local/bin/backup_acttrident.sh >> /var/log/acttrident_backup.log 2>&1
```

---

## 3. Disaster Recovery & Restoration Procedure

### Step 1: Retrieve and Decrypt Backup Dump
```bash
aws s3 cp s3://acttrident-backups-prod/database/2026/11/acttrident_db_20261119_010000.dump.gpg .
gpg --decrypt acttrident_db_20261119_010000.dump.gpg > acttrident_restore.dump
```

### Step 2: Stop Outbound Services to Prevent Inconsistent Writes
```bash
docker compose -f docker-compose.prod.yml stop app celery_worker celery_beat
```

### Step 3: Execute `pg_restore`
```bash
docker cp acttrident_restore.dump acttrident-postgres:/tmp/restore.dump

docker exec -t acttrident-postgres pg_restore \
    -U acttrident_user \
    -d acttrident_db \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    -v \
    "/tmp/restore.dump"

docker exec -t acttrident-postgres rm -f /tmp/restore.dump
rm -f acttrident_restore.dump
```

### Step 4: Verify Schema Migrations & Data Integrity
```bash
docker compose -f docker-compose.prod.yml run --rm app python -m alembic -c backend/alembic.ini current
# Expected: 0007_phase7_campaign_enhancements (head)
```

### Step 5: Restart Application & Verify Readiness
```bash
docker compose -f docker-compose.prod.yml start app celery_worker celery_beat
curl -f http://127.0.0.1:8000/health
```

---

## 4. Quarterly Disaster Recovery Drill

Every quarter:
1. Spin up a temporary staging container on an isolated host.
2. Restore the latest encrypted production snapshot into staging.
3. Verify user logins, token version increments, approval records, and CRM leads.
4. Confirm that the Global Outbound Kill Switch defaults to active in restored staging copies before workers start.
