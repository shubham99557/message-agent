"""Phase 6 operational system settings (kill switch) and transactional outbound outbox.

Revision ID: 0006_phase6_orchestration_outbox
Revises: 0005_phase5_linkedin_channel
Create Date: 2026-11-18 20:32:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0006_phase6_orchestration_outbox"
down_revision: Union[str, None] = "0005_phase5_linkedin_channel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "system_settings" not in existing_tables:
        op.create_table(
            "system_settings",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("key", sa.String(120), nullable=False),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_system_settings_id", "system_settings", ["id"])
        op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)

    if "outbound_dispatch_outbox" not in existing_tables:
        op.create_table(
            "outbound_dispatch_outbox",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("channel", sa.String(50), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
            sa.Column("idempotency_key", sa.String(160), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("next_retry_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("result_summary", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_outbound_dispatch_outbox_id", "outbound_dispatch_outbox", ["id"])
        op.create_index("ix_outbound_dispatch_outbox_channel", "outbound_dispatch_outbox", ["channel"])
        op.create_index("ix_outbound_dispatch_outbox_entity_id", "outbound_dispatch_outbox", ["entity_id"])
        op.create_index("ix_outbound_dispatch_outbox_campaign_id", "outbound_dispatch_outbox", ["campaign_id"])
        op.create_index("ix_outbound_dispatch_outbox_idempotency_key", "outbound_dispatch_outbox", ["idempotency_key"], unique=True)
        op.create_index("ix_outbound_dispatch_outbox_status", "outbound_dispatch_outbox", ["status"])
        op.create_index("ix_outbound_dispatch_outbox_next_retry_at", "outbound_dispatch_outbox", ["next_retry_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "outbound_dispatch_outbox" in existing_tables:
        op.drop_table("outbound_dispatch_outbox")

    if "system_settings" in existing_tables:
        op.drop_table("system_settings")
