"""Phase 1 baseline schema, user token_version, approval_records ledger, and indexes.

Revision ID: 0001_phase1_foundation
Revises:
Create Date: 2026-11-18 19:45:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

from app.core.database import Base
import app.models  # noqa: F401 - register all ORM models

revision: str = "0001_phase1_foundation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create any tables that do not yet exist (safe for fresh deployments and pre-existing DBs)
    Base.metadata.create_all(bind=bind, checkfirst=True)

    # 2. If upgrading an existing database, add Phase 1 security columns non-destructively
    if "users" in existing_tables:
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "token_version" not in user_cols:
            with op.batch_alter_table("users") as batch_op:
                batch_op.add_column(
                    sa.Column("token_version", sa.Integer(), nullable=False, server_default="1")
                )

    if "email_drafts" in existing_tables:
        draft_cols = {c["name"] for c in inspector.get_columns("email_drafts")}
        with op.batch_alter_table("email_drafts") as batch_op:
            if "version" not in draft_cols:
                batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
            if "content_hash" not in draft_cols:
                batch_op.add_column(sa.Column("content_hash", sa.String(64), nullable=True))
            if "approved_content_hash" not in draft_cols:
                batch_op.add_column(sa.Column("approved_content_hash", sa.String(64), nullable=True))

    # 3. Ensure approval_records table exists
    refreshed_tables = set(sa.inspect(bind).get_table_names())
    if "approval_records" not in refreshed_tables:
        op.create_table(
            "approval_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("entity_type", sa.String(50), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("approver_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("content_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_approval_records_entity", "approval_records", ["entity_type", "entity_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "approval_records" in existing_tables:
        op.drop_table("approval_records")

    if "users" in existing_tables:
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "token_version" in user_cols:
            with op.batch_alter_table("users") as batch_op:
                batch_op.drop_column("token_version")
