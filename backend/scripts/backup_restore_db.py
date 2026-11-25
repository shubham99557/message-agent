"""
Production Database Backup & Restore Utility for ActTrident AI Sales Outreach Agent.

Supports:
- SQLite (local dev/staging): uses Python sqlite3 online `.backup()` API + SHA-256 checksum manifest.
- PostgreSQL (production): invokes `pg_dump -Fc` and `pg_restore --clean --if-exists`.

Usage:
  python backend/scripts/backup_restore_db.py backup --db-url sqlite:///./acttrident.db --output ./backups/backup.db
  python backend/scripts/backup_restore_db.py restore --db-url sqlite:///./acttrident.db --input ./backups/backup.db
"""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sqlite_path_from_url(db_url: str) -> Path:
    raw = db_url.replace("sqlite:///", "", 1)
    return Path(raw).resolve()


def backup_sqlite_database(source_db: Path, output_path: Path) -> Dict[str, Any]:
    """Creates a consistent online SQLite backup with SHA-256 verification manifest."""
    if not source_db.exists():
        raise FileNotFoundError(f"Source SQLite database not found: {source_db}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    src_conn = sqlite3.connect(str(source_db))
    dst_conn = sqlite3.connect(str(output_path))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    checksum = _sha256_file(output_path)
    manifest = {
        "engine": "sqlite",
        "source": str(source_db),
        "backup_file": str(output_path),
        "sha256": checksum,
        "size_bytes": output_path.stat().st_size,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def restore_sqlite_database(backup_path: Path, target_db: Path, verify_manifest: bool = True) -> Dict[str, Any]:
    """Verifies SHA-256 manifest (if present) and restores SQLite database safely."""
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    manifest_path = backup_path.with_suffix(backup_path.suffix + ".manifest.json")
    if verify_manifest and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        actual_sha = _sha256_file(backup_path)
        if actual_sha != manifest.get("sha256"):
            raise ValueError(f"Backup checksum mismatch! Expected {manifest.get('sha256')}, got {actual_sha}")

    target_db.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(str(backup_path))
    dst_conn = sqlite3.connect(str(target_db))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    return {
        "engine": "sqlite",
        "restored_from": str(backup_path),
        "target": str(target_db),
        "restored_at": datetime.now(timezone.utc).isoformat(),
    }


def backup_postgres_database(db_url: str, output_path: Path) -> Dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["pg_dump", "-Fc", "--no-owner", f"--dbname={db_url}", "-f", str(output_path)]
    subprocess.run(cmd, check=True)
    checksum = _sha256_file(output_path)
    manifest = {
        "engine": "postgresql",
        "backup_file": str(output_path),
        "sha256": checksum,
        "size_bytes": output_path.stat().st_size,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    output_path.with_suffix(output_path.suffix + ".manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def restore_postgres_database(backup_path: Path, db_url: str) -> Dict[str, Any]:
    cmd = ["pg_restore", "--clean", "--if-exists", "--no-owner", f"--dbname={db_url}", str(backup_path)]
    subprocess.run(cmd, check=True)
    return {
        "engine": "postgresql",
        "restored_from": str(backup_path),
        "restored_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ActTrident Database Backup & Restore CLI")
    sub = parser.add_subparsers(dest="action", required=True)

    b = sub.add_parser("backup")
    b.add_argument("--db-url", default=os.getenv("DATABASE_URL", "sqlite:///./acttrident.db"))
    b.add_argument("--output", required=True)

    r = sub.add_parser("restore")
    r.add_argument("--db-url", default=os.getenv("DATABASE_URL", "sqlite:///./acttrident.db"))
    r.add_argument("--input", required=True)

    args = parser.parse_args()
    if args.action == "backup":
        out = Path(args.output).resolve()
        if args.db_url.startswith("sqlite"):
            res = backup_sqlite_database(_sqlite_path_from_url(args.db_url), out)
        else:
            res = backup_postgres_database(args.db_url, out)
        print(json.dumps(res, indent=2))
    else:
        inp = Path(args.input).resolve()
        if args.db_url.startswith("sqlite"):
            res = restore_sqlite_database(inp, _sqlite_path_from_url(args.db_url))
        else:
            res = restore_postgres_database(inp, args.db_url)
        print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
