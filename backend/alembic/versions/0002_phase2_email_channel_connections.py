"""Phase 2 channel_connections, email_send_attempts, and reply provider provenance.

Revision ID: 0002_phase2_email_connections
Revises: 0001_phase1_foundation
Create Date: 2026-11-18 19:55:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002_phase2_email_connections"
down_revision: Union[str, None] = "0001_phase1_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create channel_connections table
    if "channel_connections" not in existing_tables:
        op.create_table(
            "channel_connections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("channel", sa.String(50), nullable=False),
            sa.Column("account_identifier", sa.String(255), nullable=True),
            sa.Column("display_name", sa.String(255), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="disconnected"),
            sa.Column("is_sandbox", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("encrypted_access_token", sa.Text(), nullable=True),
            sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(), nullable=True),
            sa.Column("scopes", sa.Text(), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("connected_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_channel_connections_channel", "channel_connections", ["channel"])
        op.create_index("ix_channel_connections_status", "channel_connections", ["status"])

    # 2. Create email_send_attempts table
    if "email_send_attempts" not in existing_tables:
        op.create_table(
            "email_send_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("draft_id", sa.Integer(), sa.ForeignKey("email_drafts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("idempotency_key", sa.String(128), nullable=False),
            sa.Column("provider", sa.String(50), nullable=False),
            sa.Column("outcome", sa.String(50), nullable=False),
            sa.Column("provider_message_id", sa.String(255), nullable=True),
            sa.Column("provider_thread_id", sa.String(255), nullable=True),
            sa.Column("error_code", sa.String(100), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("attempted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_email_send_attempts_draft_id", "email_send_attempts", ["draft_id"])
        op.create_index("ix_email_send_attempts_idempotency", "email_send_attempts", ["idempotency_key"])

    # 3. Extend email_drafts with provider_thread_id and idempotency_key
    if "email_drafts" in existing_tables:
        draft_cols = {c["name"] for c in inspector.get_columns("email_drafts")}
        with op.batch_alter_table("email_drafts") as batch_op:
            if "provider_thread_id" not in draft_cols:
                batch_op.add_column(sa.Column("provider_thread_id", sa.String(255), nullable=True))
            if "idempotency_key" not in draft_cols:
                batch_op.add_column(sa.Column("idempotency_key", sa.String(128), nullable=True))

    # 4. Extend replies with provider_message_id, provider_thread_id, campaign_id
    if "replies" in existing_tables:
        reply_cols = {c["name"] for c in inspector.get_columns("replies")}
        with op.batch_alter_table("replies") as batch_op:
            if "provider_message_id" not in reply_cols:
                batch_op.add_column(sa.Column("provider_message_id", sa.String(255), nullable=True))
            if "provider_thread_id" not in reply_cols:
                batch_op.add_column(sa.Column("provider_thread_id", sa.String(255), nullable=True))
            if "campaign_id" not in reply_cols:
                batch_op.add_column(sa.Column("campaign_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "replies" in existing_tables:
        reply_cols = {c["name"] for c in inspector.get_columns("replies")}
        with op.batch_alter_table("replies") as batch_op:
            for col in ("campaign_id", "provider_thread_id", "provider_message_id"):
                if col in reply_cols:
                    batch_op.drop_column(col)

    if "email_drafts" in existing_tables:
        draft_cols = {c["name"] for c in inspector.get_columns("email_drafts")}
        with op.batch_alter_table("email_drafts") as batch_op:
            for col in ("idempotency_key", "provider_thread_id"):
                if col in draft_cols:
                    batch_op.drop_column(col)

    if "email_send_attempts" in existing_tables:
        op.drop_table("email_send_attempts")

    if "channel_connections" in existing_tables:
        op.drop_table("channel_connections")
