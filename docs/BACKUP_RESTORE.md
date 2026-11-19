# Database Backup & Disaster Recovery Guide

**Database**: PostgreSQL 18.x  
**Backup Utilities**: `pg_dump`, `pg_restore`, `tar`, `gpg`  
**Storage Targets**: Local NVMe + Encrypted Cloud Object Storage (AWS S3 / Google Cloud Storage)

---

## 1. Overview & Recovery Objectives

ActTrident maintains business-critical data including corporate prospect evidence, approval audit trails, CRM pipelines, and suppression lists. This disaster recovery plan defines procedures to achieve:

- **Recovery Point Objective (RPO)**: <= 1 hour (daily full backups + continuous WAL archiving).
- **Recovery Time Objective (RTO)**: <= 30 minutes to full service restoration.

---

## 2. Backup Strategy & Schedule

| Backup Type | Frequency | Retention Window | Storage Location |
|---|---|---|---|
| **Full Database Dump** | Daily at 01:00 UTC | 30 days | Local SSD + S3 Cold Storage |
| **Weekly Snapshot** | Sundays at 02:00 UTC | 12 weeks | Air-gapped Cloud Bucket |
| **Monthly Archive** | 1st of month | 12 months | Glacier / Deep Archive |
| **Write-Ahead Logs (WAL)** | Continuous (15-min segments) | 7 days | High-durability S3 Bucket |

---

## 3. Automated Backup Script (`backup_acttrident.sh`)

Deploy the following backup script to `/usr/local/bin/backup_acttrident.sh`:

```bash
#!/usr/bin/env bash
set -eo pipefail

BACKUP_DIR="/var/backups/acttrident"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="${BACKUP_DIR}/acttrident_db_${TIMESTAMP}.dump"
GPG_RECIPIENT="security@acttrident.com"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Initiating ActTrident PostgreSQL backup..."

# Execute binary compressed pg_dump
docker exec -t acttrident-postgres pg_dump \
    -U acttrident_user \
    -d acttrident_db \
    -F c \
    -b -v \
    -f "/tmp/backup.dump"

# Copy from container to host
docker cp acttrident-postgres:/tmp/backup.dump "${FILENAME}"
docker exec -t acttrident-postgres rm -f /tmp/backup.dump

echo "[$(date)] Backup completed: ${FILENAME} ($(du -h ${FILENAME} | cut -f1))"

# Encrypt backup with GPG
gpg --yes --batch --encrypt --recipient "${GPG_RECIPIENT}" "${FILENAME}"
rm -f "${FILENAME}"
ENCRYPTED_FILE="${FILENAME}.gpg"

echo "[$(date)] Backup encrypted: ${ENCRYPTED_FILE}"

# Sync to offsite cloud storage
aws s3 cp "${ENCRYPTED_FILE}" "s3://acttrident-backups-prod/database/$(date +%Y)/$(date +%m)/" --sse aws:kms

# Prune local backups older than 30 days
find "${BACKUP_DIR}" -type f -name "*.gpg" -mtime +30 -delete

echo "[$(date)] Backup lifecycle sync completed successfully."
```

Ensure execute permissions and configure root crontab:
```bash
chmod +x /usr/local/bin/backup_acttrident.sh
# Crontab: 0 1 * * * /usr/local/bin/backup_acttrident.sh >> /var/log/acttrident_backup.log 2>&1
```

---

## 4. Disaster Recovery & Restoration Procedure

### Step 1: Retrieve and Decrypt Backup Dump
```bash
aws s3 cp s3://acttrident-backups-prod/database/2026/11/acttrident_db_20261119_010000.dump.gpg .
gpg --decrypt acttrident_db_20261119_010000.dump.gpg > acttrident_restore.dump
```

### Step 2: Stop Outbound Services & Enable Maintenance Mode
Halt the application and Celery workers to prevent concurrent writes:
```bash
docker compose -f docker-compose.prod.yml stop app celery_worker celery_beat
```

### Step 3: Execute `pg_restore`
Restore the custom-format dump into the target database:
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

### Step 4: Run Alembic Migration Verification
Verify that schema migrations match the current codebase:
```bash
docker compose -f docker-compose.prod.yml run --rm app python -m alembic -c backend/alembic.ini current
```

### Step 5: Restart Application & Verify Integrity
```bash
docker compose -f docker-compose.prod.yml start app celery_worker celery_beat
curl -f https://sales.acttrident.com/api/v1/jobs/health
```

---

## 5. Periodic Disaster Recovery Drill

Disaster recovery drills must be performed quarterly in a staging sandbox:
1. Restore the latest encrypted production snapshot into the staging database.
2. Confirm user accounts, token versions, companies, campaigns, and approval records exist.
3. Verify that the Global Kill Switch defaults to active in the restored staging copy before any worker starts.
