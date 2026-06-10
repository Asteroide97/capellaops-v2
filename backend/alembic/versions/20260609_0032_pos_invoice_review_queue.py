"""Add POS fiscal review queue fields for billing preparation.

Revision ID: 20260609_0032
Revises: 20260609_0031
Create Date: 2026-06-09 23:55:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260609_0032"
down_revision: str | None = "20260609_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INVOICE_REVIEW_STATUS_CHECK = (
    "factura_revision_estado IS NULL OR factura_revision_estado IN "
    "('pendiente_datos', 'lista_para_facturar', 'en_revision', 'observada', 'preparada', 'descartada')"
)


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("ventas", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("factura_revision_estado", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("factura_revision_notas", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("factura_revisada_por_user_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("factura_revisada_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("factura_preparada_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("factura_descartada_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("factura_error_datos", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_ventas_factura_revisada_por_user_id_usuarios",
            "usuarios",
            ["factura_revisada_por_user_id"],
            ["id"],
        )
        batch_op.create_check_constraint(
            "ck_venta_factura_revision_estado",
            INVOICE_REVIEW_STATUS_CHECK,
        )
        batch_op.create_index("ix_ventas_factura_revision_estado", ["factura_revision_estado"], unique=False)
        batch_op.create_index("ix_ventas_factura_revisada_at", ["factura_revisada_at"], unique=False)
        batch_op.create_index("ix_ventas_factura_revisada_por_user_id", ["factura_revisada_por_user_id"], unique=False)


def downgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("ventas", **batch_kwargs) as batch_op:
        batch_op.drop_index("ix_ventas_factura_revisada_por_user_id")
        batch_op.drop_index("ix_ventas_factura_revisada_at")
        batch_op.drop_index("ix_ventas_factura_revision_estado")
        batch_op.drop_constraint("ck_venta_factura_revision_estado", type_="check")
        batch_op.drop_constraint("fk_ventas_factura_revisada_por_user_id_usuarios", type_="foreignkey")
        batch_op.drop_column("factura_error_datos")
        batch_op.drop_column("factura_descartada_at")
        batch_op.drop_column("factura_preparada_at")
        batch_op.drop_column("factura_revisada_at")
        batch_op.drop_column("factura_revisada_por_user_id")
        batch_op.drop_column("factura_revision_notas")
        batch_op.drop_column("factura_revision_estado")
