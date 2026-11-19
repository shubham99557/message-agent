"""Phase 4 discovery provenance, verification status, and research confidence/missing info.

Revision ID: 0004_phase4_discovery_provenance
Revises: 0003_phase3_whatsapp_sync
Create Date: 2026-11-18 20:10:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004_phase4_discovery_provenance"
down_revision: Union[str, None] = "0003_phase3_whatsapp_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "companies" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("companies")}
        with op.batch_alter_table("companies") as batch_op:
            if "verification_status" not in cols:
                batch_op.add_column(sa.Column("verification_status", sa.String(50), nullable=False, server_default="unverified"))
            if "verification_method" not in cols:
                batch_op.add_column(sa.Column("verification_method", sa.String(100), nullable=True))

    if "contact_sources" in existing_tables:
        scols = {c["name"] for c in inspector.get_columns("contact_sources")}
        with op.batch_alter_table("contact_sources") as batch_op:
            if "verification_status" not in scols:
                batch_op.add_column(sa.Column("verification_status", sa.String(50), nullable=False, server_default="unverified"))
            if "verification_method" not in scols:
                batch_op.add_column(sa.Column("verification_method", sa.String(100), nullable=True))

    if "research_reports" in existing_tables:
        rcols = {c["name"] for c in inspector.get_columns("research_reports")}
        with op.batch_alter_table("research_reports") as batch_op:
            if "missing_information" not in rcols:
                batch_op.add_column(sa.Column("missing_information", sa.Text(), nullable=True))
            if "confidence_level" not in rcols:
                batch_op.add_column(sa.Column("confidence_level", sa.Float(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "research_reports" in existing_tables:
        rcols = {c["name"] for c in inspector.get_columns("research_reports")}
        with op.batch_alter_table("research_reports") as batch_op:
            for col in ("confidence_level", "missing_information"):
                if col in rcols:
                    batch_op.drop_column(col)

    if "contact_sources" in existing_tables:
        scols = {c["name"] for c in inspector.get_columns("contact_sources")}
        with op.batch_alter_table("contact_sources") as batch_op:
            for col in ("verification_method", "verification_status"):
                if col in scols:
                    batch_op.drop_column(col)

    if "companies" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("companies")}
        with op.batch_alter_table("companies") as batch_op:
            for col in ("verification_method", "verification_status"):
                if col in cols:
                    batch_op.drop_column(col)
