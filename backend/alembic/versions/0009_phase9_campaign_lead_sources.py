"""Phase 9: campaign-scoped lead sources and discovery-run campaign link.

Revision ID: 0009_phase9_campaign_lead_sources
Revises: 0008_phase8_production_hardening_constraints
Create Date: 2026-11-25 12:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0009_phase9_campaign_lead_sources"
down_revision: Union[str, None] = "0008_phase8_production_hardening_constraints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent like 0001-0008: 0001 runs Base.metadata.create_all, and desktop/dev mode
    # syncs columns at startup, so the table/column may already exist.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "campaign_lead_sources" not in existing_tables:
        op.create_table(
            "campaign_lead_sources",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("discovery_run_id", sa.Integer(), sa.ForeignKey("discovery_runs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("source", sa.String(50), nullable=False, server_default="discovery_pipeline"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("campaign_id", "company_id", name="uq_campaign_lead_source_company"),
        )
        op.create_index("ix_campaign_lead_sources_id", "campaign_lead_sources", ["id"])
        op.create_index("ix_campaign_lead_sources_campaign_id", "campaign_lead_sources", ["campaign_id"])
        op.create_index("ix_campaign_lead_sources_company_id", "campaign_lead_sources", ["company_id"])

    run_columns = {c["name"] for c in inspector.get_columns("discovery_runs")}
    if "campaign_id" not in run_columns:
        with op.batch_alter_table("discovery_runs") as batch_op:
            batch_op.add_column(sa.Column("campaign_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_discovery_runs_campaign_id", "campaigns", ["campaign_id"], ["id"], ondelete="SET NULL"
            )
    run_indexes = {i["name"] for i in sa.inspect(bind).get_indexes("discovery_runs")}
    if "ix_discovery_runs_campaign_id" not in run_indexes:
        op.create_index("ix_discovery_runs_campaign_id", "discovery_runs", ["campaign_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    run_columns = {c["name"] for c in inspector.get_columns("discovery_runs")}
    if "campaign_id" in run_columns:
        run_indexes = {i["name"] for i in inspector.get_indexes("discovery_runs")}
        fks = {fk.get("name") for fk in inspector.get_foreign_keys("discovery_runs")}
        with op.batch_alter_table("discovery_runs") as batch_op:
            if "ix_discovery_runs_campaign_id" in run_indexes:
                batch_op.drop_index("ix_discovery_runs_campaign_id")
            if "fk_discovery_runs_campaign_id" in fks:
                batch_op.drop_constraint("fk_discovery_runs_campaign_id", type_="foreignkey")
            batch_op.drop_column("campaign_id")
    if "campaign_lead_sources" in set(inspector.get_table_names()):
        op.drop_table("campaign_lead_sources")
