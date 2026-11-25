# ACTTRIDENT — LOCAL DATABASE, STORAGE & BACKUP RUNBOOK

**Target Storage:** `%LOCALAPPDATA%\ActTrident\`  
**Engine:** SQLite 3 with Write-Ahead Logging (WAL) Mode  

---

## 1. Directory Structure

ActTrident organizes all local application data inside your user profile to prevent accidental deletion during updates:

```text
%LOCALAPPDATA%\ActTrident\
├── data/
│   ├── acttrident.db          # Primary SQLite database
│   ├── acttrident.db-wal      # Write-Ahead Log journal (active transactions)
│   └── acttrident.db-shm      # Shared memory index
├── backups/                   # Point-in-time database snapshots
│   ├── acttrident_backup_*.db
│   └── acttrident_backup_*.manifest.json
├── exports/                   # CRM CSV streaming exports
├── files/                     # Downloaded prospect attachments / evidence
├── logs/                      # Runtime server and audit logs
│   └── acttrident_server.log
└── config/                    # Custom local configurations
```

---

## 2. SQLite Engine Optimization

1. **Write-Ahead Logging (WAL):** Enabled automatically (`PRAGMA journal_mode=WAL`). Allows concurrent readers while background workers write task records, eliminating database lock errors.
2. **Foreign Key Constraints:** Enforced strictly (`PRAGMA foreign_keys=ON`) for data integrity.
3. **Busy Timeout:** Configured to 5,000 ms (`PRAGMA busy_timeout=5000`) to queue concurrent operations cleanly.

---

## 3. Creating Backups

### Method A: Through Desktop UI
1. Navigate to **Settings** in the ActTrident sidebar.
2. Scroll to the **Local Desktop Persistent Storage** panel.
3. Click **Create Instant Backup**.
4. A point-in-time backup with SHA-256 checksum manifest is generated in `backups/`.

### Method B: Via CLI
```powershell
python backend/scripts/backup_restore_db.py backup --output "%LOCALAPPDATA%\ActTrident\backups\manual_backup.db"
```

---

## 4. Restoring From a Backup

To restore your database from a previous snapshot:
```powershell
# 1. Stop ActTrident
.\scripts\stop_acttrident_desktop.bat

# 2. Run Restore Command
python backend/scripts/backup_restore_db.py restore --db-url "sqlite:///%LOCALAPPDATA%\ActTrident\data\acttrident.db" --input "%LOCALAPPDATA%\ActTrident\backups\manual_backup.db"

# 3. Restart ActTrident
.\scripts\start_acttrident_desktop.bat
```

---

## 5. Safe Uninstallation & Data Retention

If you uninstall or move the application code, your business data, research dossiers, leads, and campaigns remain safely stored in `%LOCALAPPDATA%\ActTrident\data\acttrident.db`.  
To completely remove all data, manually delete the `%LOCALAPPDATA%\ActTrident` folder.
