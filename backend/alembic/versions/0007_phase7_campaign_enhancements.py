"""Phase 7 campaign targeting criteria, scheduling limits, and extended statuses.

Revision ID: 0007_phase7_campaign_enhancements
Revises: 0006_phase6_orchestration_outbox
Create Date: 2026-11-19 00:30:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0007_phase7_campaign_enhancements"
down_revision: Union[str, None] = "0006_phase6_orchestration_outbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("campaigns")}
    draft_columns = {col["name"] for col in inspector.get_columns("email_drafts")}

    if "business_type" not in existing_columns:
        op.add_column("campaigns", sa.Column("business_type", sa.String(255), nullable=True))
    if "company_size" not in existing_columns:
        op.add_column("campaigns", sa.Column("company_size", sa.String(100), nullable=True))
    if "min_devices" not in existing_columns:
        op.add_column("campaigns", sa.Column("min_devices", sa.Integer(), nullable=True, server_default="5"))
    if "min_score" not in existing_columns:
        op.add_column("campaigns", sa.Column("min_score", sa.Float(), nullable=True, server_default="0.0"))
    if "allowed_channels" not in existing_columns:
        op.add_column("campaigns", sa.Column("allowed_channels", sa.String(255), nullable=True, server_default="email,whatsapp,linkedin"))
    if "total_email_limit" not in existing_columns:
        op.add_column("campaigns", sa.Column("total_email_limit", sa.Integer(), nullable=True))
    if "start_date" not in existing_columns:
        op.add_column("campaigns", sa.Column("start_date", sa.DateTime(), nullable=True))
    if "end_date" not in existing_columns:
        op.add_column("campaigns", sa.Column("end_date", sa.DateTime(), nullable=True))

    if "scheduled_at" not in draft_columns:
        op.add_column("email_drafts", sa.Column("scheduled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("campaigns")}
    draft_columns = {col["name"] for col in inspector.get_columns("email_drafts")}

    if "scheduled_at" in draft_columns:
        op.drop_column("email_drafts", "scheduled_at")

    for col in (
        "end_date",
        "start_date",
        "total_email_limit",
        "allowed_channels",
        "min_score",
        "min_devices",
        "company_size",
        "business_type",
    ):
        if col in existing_columns:
            op.drop_column("campaigns", col)
