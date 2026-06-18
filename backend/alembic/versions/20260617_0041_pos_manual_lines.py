"""Add manual and service POS sale lines.

Revision ID: 20260617_0041
Revises: 20260617_0040
Create Date: 2026-06-17 18:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260617_0041"
down_revision: str | None = "20260617_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}

    with op.batch_alter_table("ventas_detalles", **batch_kwargs) as batch_op:
        batch_op.add_column(
            sa.Column("tipo_linea", sa.String(length=20), nullable=False, server_default=sa.text("'material'"))
        )
        batch_op.add_column(sa.Column("descripcion_manual", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("es_inventariable", sa.Boolean(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("costo_unitario_manual", sa.Numeric(18, 4), nullable=True))
        batch_op.add_column(
            sa.Column("impuesto_tasa", sa.Numeric(18, 4), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("impuesto_linea", sa.Numeric(18, 4), nullable=False, server_default="0")
        )
        batch_op.alter_column("material_id", existing_type=sa.String(length=36), nullable=True)
        batch_op.create_check_constraint(
            "ck_venta_detalle_tipo_linea",
            "tipo_linea IN ('material', 'manual', 'servicio')",
        )
        batch_op.create_check_constraint(
            "ck_venta_detalle_impuesto_tasa_nonnegative",
            "impuesto_tasa >= 0",
        )
        batch_op.create_check_constraint(
            "ck_venta_detalle_impuesto_linea_nonnegative",
            "impuesto_linea >= 0",
        )
        batch_op.create_check_constraint(
            "ck_venta_detalle_linea_requerida",
            "("
            "tipo_linea = 'material' AND material_id IS NOT NULL"
            ") OR ("
            "tipo_linea IN ('manual', 'servicio') AND descripcion_manual IS NOT NULL"
            ")",
        )

    op.create_index("ix_ventas_detalles_tipo_linea", "ventas_detalles", ["tipo_linea"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ventas_detalles_tipo_linea", table_name="ventas_detalles")

    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("ventas_detalles", **batch_kwargs) as batch_op:
        batch_op.drop_constraint("ck_venta_detalle_linea_requerida", type_="check")
        batch_op.drop_constraint("ck_venta_detalle_impuesto_linea_nonnegative", type_="check")
        batch_op.drop_constraint("ck_venta_detalle_impuesto_tasa_nonnegative", type_="check")
        batch_op.drop_constraint("ck_venta_detalle_tipo_linea", type_="check")
        batch_op.alter_column("material_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.drop_column("impuesto_linea")
        batch_op.drop_column("impuesto_tasa")
        batch_op.drop_column("costo_unitario_manual")
        batch_op.drop_column("es_inventariable")
        batch_op.drop_column("descripcion_manual")
        batch_op.drop_column("tipo_linea")
