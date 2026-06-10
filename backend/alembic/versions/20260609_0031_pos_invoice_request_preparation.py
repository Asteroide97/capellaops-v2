"""Prepare POS sales for invoice requests without CFDI stamping.

Revision ID: 20260609_0031
Revises: 20260609_0029
Create Date: 2026-06-09 23:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260609_0031"
down_revision: str | None = "20260609_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INVOICE_STATUS_CHECK = (
    "factura_estado IN ('no_solicitada', 'solicitada', 'pendiente_datos', "
    "'lista_para_facturar', 'facturada', 'cancelada')"
)


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("ventas", **batch_kwargs) as batch_op:
        batch_op.add_column(
            sa.Column("factura_estado", sa.String(length=30), nullable=False, server_default=sa.text("'no_solicitada'"))
        )
        batch_op.add_column(sa.Column("factura_solicitada_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("factura_cliente_nombre", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("factura_rfc", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("factura_razon_social", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("factura_email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("factura_uso_cfdi", sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column("factura_regimen_fiscal", sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column("factura_codigo_postal", sa.String(length=12), nullable=True))
        batch_op.add_column(sa.Column("factura_notas", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("factura_requiere_factura_global", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.create_check_constraint("ck_venta_factura_estado", INVOICE_STATUS_CHECK)
        batch_op.create_index("ix_ventas_factura_estado", ["factura_estado"], unique=False)
        batch_op.create_index("ix_ventas_factura_solicitada_at", ["factura_solicitada_at"], unique=False)
        batch_op.create_index("ix_ventas_factura_rfc", ["factura_rfc"], unique=False)

    op.execute("UPDATE ventas SET factura_estado = 'no_solicitada' WHERE factura_estado IS NULL")
    op.execute("UPDATE ventas SET factura_requiere_factura_global = 0 WHERE factura_requiere_factura_global IS NULL")


def downgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("ventas", **batch_kwargs) as batch_op:
        batch_op.drop_index("ix_ventas_factura_rfc")
        batch_op.drop_index("ix_ventas_factura_solicitada_at")
        batch_op.drop_index("ix_ventas_factura_estado")
        batch_op.drop_constraint("ck_venta_factura_estado", type_="check")
        batch_op.drop_column("factura_requiere_factura_global")
        batch_op.drop_column("factura_notas")
        batch_op.drop_column("factura_codigo_postal")
        batch_op.drop_column("factura_regimen_fiscal")
        batch_op.drop_column("factura_uso_cfdi")
        batch_op.drop_column("factura_email")
        batch_op.drop_column("factura_razon_social")
        batch_op.drop_column("factura_rfc")
        batch_op.drop_column("factura_cliente_nombre")
        batch_op.drop_column("factura_solicitada_at")
        batch_op.drop_column("factura_estado")
