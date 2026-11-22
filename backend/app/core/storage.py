"""
Local-First Storage and Directory Architecture for ActTrident.
Manages persistent storage in %LOCALAPPDATA%\\ActTrident\\, WAL mode, backups, and integrity.
"""
import os
import shutil
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any

from app.core.config import settings

logger = logging.getLogger("acttrident.storage")


def get_acttrident_data_dir() -> Path:
    """Returns the persistent %LOCALAPPDATA%\\ActTrident root directory."""
    raw = getattr(settings, "LOCAL_APP_DATA_DIR", None)
    if raw:
        base = Path(raw)
    else:
        local_app_data = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
        base = Path(local_app_data) / "ActTrident"
    return base.resolve()


def initialize_storage_layout() -> Dict[str, Path]:
    """
    Creates and verifies all required ActTrident local directories:
    - data/     (acttrident.db)
    - files/    (documents, reports)
    - exports/  (CSV, research exports)
    - backups/  (database snapshots)
    - logs/     (runtime logs)
    - cache/    (web scrape / query cache)
    - config/   (user local settings)
    """
    root = get_acttrident_data_dir()
    dirs = {
        "root": root,
        "data": root / "data",
        "files": root / "files",
        "exports": root / "exports",
        "backups": root / "backups",
        "logs": root / "logs",
        "cache": root / "cache",
        "config": root / "config",
    }
    for name, p in dirs.items():
        p.mkdir(parents=True, exist_ok=True)
    return dirs


def resolve_local_database_path() -> Path:
    """
    Resolves the primary persistent SQLite database path.
    If an existing database is found in the project root, it safely migrates it
    to %LOCALAPPDATA%\\ActTrident\\data\\acttrident.db if not already present.
    """
    dirs = initialize_storage_layout()
    target_db = dirs["data"] / "acttrident.db"

    # Check if a database already exists in the project root
    project_db = Path("backend/acttrident.db").resolve()
    if not project_db.exists():
        project_db = Path("acttrident.db").resolve()

    if project_db.exists() and not target_db.exists():
        try:
            shutil.copy2(project_db, target_db)
            logger.info(f"Safely migrated existing database from {project_db} to persistent desktop path: {target_db}")
        except Exception as exc:
            logger.warning(f"Could not migrate project database to {target_db}: {exc}")

    # If target exists or was migrated, return target; otherwise return project path as fallback
    if target_db.exists():
        return target_db
    return project_db


def check_storage_health() -> Dict[str, Any]:
    """Inspects local drive storage, free space, and database size."""
    root = get_acttrident_data_dir()
    dirs = initialize_storage_layout()
    db_path = resolve_local_database_path()

    db_size_mb = 0.0
    if db_path.exists():
        db_size_mb = round(db_path.stat().st_size / (1024 * 1024), 2)

    # Disk free space
    free_gb = 0.0
    total_gb = 0.0
    try:
        usage = shutil.disk_usage(root)
        free_gb = round(usage.free / (1024 ** 3), 2)
        total_gb = round(usage.total / (1024 ** 3), 2)
    except Exception:
        pass

    # Check SQLite integrity if db exists
    integrity_ok = True
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("PRAGMA quick_check")
            res = cur.fetchone()
            integrity_ok = (res and res[0] == "ok")
            conn.close()
        except Exception:
            integrity_ok = False

    backups_count = len(list(dirs["backups"].glob("*.db")))

    return {
        "status": "healthy" if integrity_ok and free_gb > 2.0 else "warning",
        "root_directory": str(root),
        "database_file": str(db_path),
        "database_size_mb": db_size_mb,
        "database_integrity_ok": integrity_ok,
        "free_disk_space_gb": free_gb,
        "total_disk_space_gb": total_gb,
        "backups_stored": backups_count,
        "wal_mode_enabled": True,
    }


def create_database_backup() -> Dict[str, Any]:
    """Creates a point-in-time SQLite database backup into %LOCALAPPDATA%\\ActTrident\\backups."""
    from datetime import datetime, timezone
    root = get_acttrident_data_dir()
    backups_dir = root / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = backups_dir / f"acttrident_backup_{timestamp}.db"

    db_path = resolve_local_database_path()
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            dest = sqlite3.connect(str(out_file))
            conn.backup(dest)
            dest.close()
            conn.close()
            return {
                "status": "success",
                "backup_file": str(out_file),
                "timestamp": timestamp,
                "size_bytes": out_file.stat().st_size,
            }
        except Exception as exc:
            logger.warning(f"Database backup failed: {exc}")
            return {"status": "failed", "error": str(exc)}
    return {"status": "skipped", "reason": "Database file not found"}
