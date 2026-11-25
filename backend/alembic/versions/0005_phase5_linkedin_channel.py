"""Phase 5 LinkedIn authorized outreach channel table.

Revision ID: 0005_phase5_linkedin_channel
Revises: 0004_phase4_discovery_provenance
Create Date: 2026-11-18 20:25:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005_phase5_linkedin_channel"
down_revision: Union[str, None] = "0004_phase4_discovery_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "linkedin_messages" not in existing_tables:
        op.create_table(
            "linkedin_messages",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
            sa.Column("recipient_name", sa.String(255), nullable=True),
            sa.Column("recipient_profile_url", sa.String(500), nullable=False),
            sa.Column("message_type", sa.String(50), nullable=False, server_default="connection_note"),
            sa.Column("tone", sa.String(100), nullable=False, server_default="Consultative"),
            sa.Column("message_body", sa.Text(), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("approval_status", sa.String(50), nullable=False, server_default="draft"),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("delivery_mode", sa.String(50), nullable=False, server_default="manual_handoff"),
            sa.Column("provider_message_id", sa.String(255), nullable=True),
            sa.Column("idempotency_key", sa.String(255), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("sent_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_linkedin_messages_id", "linkedin_messages", ["id"])
        op.create_index("ix_linkedin_messages_company_id", "linkedin_messages", ["company_id"])
        op.create_index("ix_linkedin_messages_campaign_id", "linkedin_messages", ["campaign_id"])
        op.create_index("ix_linkedin_messages_content_hash", "linkedin_messages", ["content_hash"])
        op.create_index("ix_linkedin_messages_approval_status", "linkedin_messages", ["approval_status"])
        op.create_index("ix_linkedin_messages_provider_message_id", "linkedin_messages", ["provider_message_id"])
        op.create_index("ix_linkedin_messages_idempotency_key", "linkedin_messages", ["idempotency_key"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "linkedin_messages" in existing_tables:
        op.drop_table("linkedin_messages")
