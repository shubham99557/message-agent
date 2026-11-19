"""
Secure CLI Administrator Provisioning Utility for Production & Staging.

Usage:
    python backend/scripts/provision_admin.py --email admin@acttrident.ai --name "Operations Admin"
    (Prompts securely for password without echoing to terminal or shell history.)
"""
import argparse
import getpass
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.schemas.auth import AdminUserCreate
from app.services.auth_service import create_user, get_user_by_email
from app.core.audit import record_audit_log


def main():
    parser = argparse.ArgumentParser(description="Provision an ActTrident administrator account securely.")
    parser.add_argument("--email", required=True, help="Administrator email address")
    parser.add_argument("--name", required=True, help="Administrator full name")
    args = parser.parse_args()

    password = getpass.getpass("Enter strong password (min 8 chars, upper, lower, digit): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Error: Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    user_in = AdminUserCreate(email=args.email, full_name=args.name, password=password, role="admin")

    db = SessionLocal()
    try:
        existing = get_user_by_email(db, user_in.email)
        if existing:
            print(f"Error: User '{user_in.email}' already exists (id={existing.id}).", file=sys.stderr)
            sys.exit(1)
        admin = create_user(db, user_in, role="admin")
        record_audit_log(
            db=db,
            action="cli_provision_admin",
            entity_type="user",
            entity_id=str(admin.id),
            details={"email": admin.email, "role": "admin"}
        )
        print(f"Provisioned administrator '{admin.email}' (id={admin.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
