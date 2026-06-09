"""Add POS ticket delivery log.

Revision ID: 20260609_0030
Revises: 20260609_0029
Create Date: 2026-06-09 23:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260609_0030"
down_revision: str | None = "20260609_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pos_ticket_deliveries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("venta_id", sa.String(length=36), nullable=False),
        sa.Column("canal", sa.String(length=20), nullable=False),
        sa.Column("destino", sa.String(length=255), nullable=False),
        sa.Column("estatus", sa.String(length=20), nullable=False),
        sa.Column("proveedor", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("canal IN ('email', 'sms')", name="ck_pos_ticket_delivery_canal"),
        sa.CheckConstraint("estatus IN ('enviado', 'fallido')", name="ck_pos_ticket_delivery_estatus"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["venta_id"], ["ventas.id"]),
        sa.ForeignKeyConstraint(["sent_by_user_id"], ["usuarios.id"]),
    )
    op.create_index("ix_pos_ticket_deliveries_empresa_id", "pos_ticket_deliveries", ["empresa_id"], unique=False)
    op.create_index("ix_pos_ticket_deliveries_venta_id", "pos_ticket_deliveries", ["venta_id"], unique=False)
    op.create_index("ix_pos_ticket_deliveries_canal", "pos_ticket_deliveries", ["canal"], unique=False)
    op.create_index("ix_pos_ticket_deliveries_estatus", "pos_ticket_deliveries", ["estatus"], unique=False)
    op.create_index(
        "ix_pos_ticket_deliveries_sent_by_user_id",
        "pos_ticket_deliveries",
        ["sent_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pos_ticket_deliveries_sent_by_user_id", table_name="pos_ticket_deliveries")
    op.drop_index("ix_pos_ticket_deliveries_estatus", table_name="pos_ticket_deliveries")
    op.drop_index("ix_pos_ticket_deliveries_canal", table_name="pos_ticket_deliveries")
    op.drop_index("ix_pos_ticket_deliveries_venta_id", table_name="pos_ticket_deliveries")
    op.drop_index("ix_pos_ticket_deliveries_empresa_id", table_name="pos_ticket_deliveries")
    op.drop_table("pos_ticket_deliveries")
