"""Add requisition links for inventory connections phase 1."""

from alembic import op
import sqlalchemy as sa


revision = "20260527_0010"
down_revision = "20260526_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("requisiciones") as batch_op:
        batch_op.add_column(sa.Column("proveedor_sugerido_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("orden_compra_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_requisiciones_proveedor_sugerido_id",
            "proveedores",
            ["proveedor_sugerido_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_requisiciones_orden_compra_id",
            "ordenes_compra",
            ["orden_compra_id"],
            ["id"],
        )
        batch_op.create_index("ix_requisiciones_proveedor_sugerido_id", ["proveedor_sugerido_id"], unique=False)
        batch_op.create_index("ix_requisiciones_orden_compra_id", ["orden_compra_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("requisiciones") as batch_op:
        batch_op.drop_index("ix_requisiciones_orden_compra_id")
        batch_op.drop_index("ix_requisiciones_proveedor_sugerido_id")
        batch_op.drop_constraint("fk_requisiciones_orden_compra_id", type_="foreignkey")
        batch_op.drop_constraint("fk_requisiciones_proveedor_sugerido_id", type_="foreignkey")
        batch_op.drop_column("orden_compra_id")
        batch_op.drop_column("proveedor_sugerido_id")
