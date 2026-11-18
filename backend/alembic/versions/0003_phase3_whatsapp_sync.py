"""Phase 3 WhatsApp Meta template sync provenance and message idempotency key.

Revision ID: 0003_phase3_whatsapp_sync
Revises: 0002_phase2_email_connections
Create Date: 2026-11-18 20:05:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003_phase3_whatsapp_sync"
down_revision: Union[str, None] = "0002_phase2_email_connections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "whatsapp_templates" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("whatsapp_templates")}
        with op.batch_alter_table("whatsapp_templates") as batch_op:
            if "meta_template_id" not in cols:
                batch_op.add_column(sa.Column("meta_template_id", sa.String(255), nullable=True))
            if "synced_from_meta" not in cols:
                batch_op.add_column(sa.Column("synced_from_meta", sa.Boolean(), nullable=False, server_default=sa.false()))
            if "last_synced_at" not in cols:
                batch_op.add_column(sa.Column("last_synced_at", sa.DateTime(), nullable=True))

    if "whatsapp_messages" in existing_tables:
        mcols = {c["name"] for c in inspector.get_columns("whatsapp_messages")}
        with op.batch_alter_table("whatsapp_messages") as batch_op:
            if "idempotency_key" not in mcols:
                batch_op.add_column(sa.Column("idempotency_key", sa.String(128), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "whatsapp_messages" in existing_tables:
        mcols = {c["name"] for c in inspector.get_columns("whatsapp_messages")}
        if "idempotency_key" in mcols:
            with op.batch_alter_table("whatsapp_messages") as batch_op:
                batch_op.drop_column("idempotency_key")

    if "whatsapp_templates" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("whatsapp_templates")}
        with op.batch_alter_table("whatsapp_templates") as batch_op:
            for col in ("last_synced_at", "synced_from_meta", "meta_template_id"):
                if col in cols:
                    batch_op.drop_column(col)
