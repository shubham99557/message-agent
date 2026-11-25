"""Phase 8 production hardening constraints and indexes.

Revision ID: 0008_phase8_production_hardening_constraints
Revises: 0007_phase7_campaign_enhancements
Create Date: 2026-11-19 18:00:00
"""
from typing import Sequence, Union
from alembic import op, context
import sqlalchemy as sa

revision: str = "0008_phase8_production_hardening_constraints"
down_revision: Union[str, None] = "0007_phase7_campaign_enhancements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect_name = context.get_context().dialect.name if context.get_context() else "sqlite"

    if context.is_offline_mode():
        if dialect_name == "sqlite":
            op.create_index("uq_campaign_recipient_company", "campaign_recipients", ["campaign_id", "company_id"], unique=True)
        else:
            op.create_unique_constraint("uq_campaign_recipient_company", "campaign_recipients", ["campaign_id", "company_id"])
        op.create_index("ix_suppression_identifier_channel", "suppression_list", ["identifier", "channel"], unique=False)
        op.create_index("ix_email_drafts_campaign_recipient", "email_drafts", ["campaign_id", "recipient_email"], unique=False)
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Unique constraint on campaign_recipients (campaign_id, company_id)
    existing_uqs = []
    try:
        existing_uqs = [uq["name"] for uq in inspector.get_unique_constraints("campaign_recipients")]
    except Exception:
        pass

    if "uq_campaign_recipient_company" not in existing_uqs:
        if dialect_name == "sqlite":
            with op.batch_alter_table("campaign_recipients") as batch_op:
                batch_op.create_unique_constraint("uq_campaign_recipient_company", ["campaign_id", "company_id"])
        else:
            op.create_unique_constraint("uq_campaign_recipient_company", "campaign_recipients", ["campaign_id", "company_id"])

    # 2. Composite index on suppression_list (identifier, channel)
    existing_suppression_indexes = []
    try:
        existing_suppression_indexes = [idx["name"] for idx in inspector.get_indexes("suppression_list")]
    except Exception:
        pass

    if "ix_suppression_identifier_channel" not in existing_suppression_indexes:
        op.create_index(
            "ix_suppression_identifier_channel",
            "suppression_list",
            ["identifier", "channel"],
            unique=False
        )

    # 3. Composite index on email_drafts (campaign_id, recipient_email)
    existing_draft_indexes = []
    try:
        existing_draft_indexes = [idx["name"] for idx in inspector.get_indexes("email_drafts")]
    except Exception:
        pass

    if "ix_email_drafts_campaign_recipient" not in existing_draft_indexes:
        op.create_index(
            "ix_email_drafts_campaign_recipient",
            "email_drafts",
            ["campaign_id", "recipient_email"],
            unique=False
        )


def downgrade() -> None:
    dialect_name = context.get_context().dialect.name if context.get_context() else "sqlite"

    if context.is_offline_mode():
        op.drop_index("ix_email_drafts_campaign_recipient", table_name="email_drafts")
        op.drop_index("ix_suppression_identifier_channel", table_name="suppression_list")
        if dialect_name == "sqlite":
            op.drop_index("uq_campaign_recipient_company", table_name="campaign_recipients")
        else:
            op.drop_constraint("uq_campaign_recipient_company", "campaign_recipients", type_="unique")
        return

    try:
        op.drop_index("ix_email_drafts_campaign_recipient", table_name="email_drafts")
    except Exception:
        pass

    try:
        op.drop_index("ix_suppression_identifier_channel", table_name="suppression_list")
    except Exception:
        pass

    try:
        if dialect_name == "sqlite":
            with op.batch_alter_table("campaign_recipients") as batch_op:
                batch_op.drop_constraint("uq_campaign_recipient_company", type_="unique")
        else:
            op.drop_constraint("uq_campaign_recipient_company", "campaign_recipients", type_="unique")
    except Exception:
        pass
