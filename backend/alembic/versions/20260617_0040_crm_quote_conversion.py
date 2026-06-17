"""Add CRM quote conversion links to PM projects and POS sales.

Revision ID: 20260617_0040
Revises: 20260617_0039
Create Date: 2026-06-17 15:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260617_0040"
down_revision: str | None = "20260617_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}

    with op.batch_alter_table("crm_cotizaciones", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("proyecto_pm_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("venta_pos_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("convertida_a_proyecto_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("convertida_a_venta_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key("fk_crm_cotizaciones_proyecto_pm_id", "pm_proyectos", ["proyecto_pm_id"], ["id"])
        batch_op.create_foreign_key("fk_crm_cotizaciones_venta_pos_id", "ventas", ["venta_pos_id"], ["id"])

    op.create_index("ix_crm_cotizaciones_proyecto_pm_id", "crm_cotizaciones", ["proyecto_pm_id"], unique=False)
    op.create_index("ix_crm_cotizaciones_venta_pos_id", "crm_cotizaciones", ["venta_pos_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_crm_cotizaciones_venta_pos_id", table_name="crm_cotizaciones")
    op.drop_index("ix_crm_cotizaciones_proyecto_pm_id", table_name="crm_cotizaciones")

    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("crm_cotizaciones", **batch_kwargs) as batch_op:
        batch_op.drop_constraint("fk_crm_cotizaciones_venta_pos_id", type_="foreignkey")
        batch_op.drop_constraint("fk_crm_cotizaciones_proyecto_pm_id", type_="foreignkey")
        batch_op.drop_column("convertida_a_venta_at")
        batch_op.drop_column("convertida_a_proyecto_at")
        batch_op.drop_column("venta_pos_id")
        batch_op.drop_column("proyecto_pm_id")
