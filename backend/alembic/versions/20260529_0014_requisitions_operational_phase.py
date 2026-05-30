"""Extend requisitions for operational fulfillment flow."""

from alembic import op
import sqlalchemy as sa


revision = "20260529_0014"
down_revision = "20260529_0013"
branch_labels = None
depends_on = None


REQUISITION_STATUS_CHECK = (
    "estatus IN ('borrador', 'enviada', 'aprobada', 'rechazada', 'cancelada', "
    "'parcial', 'surtida', 'convertida_a_oc')"
)


def upgrade() -> None:
    with op.batch_alter_table("requisiciones", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("es_proyecto", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("proyecto_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("proyecto_nombre_snapshot", sa.String(length=180), nullable=True))
        batch_op.drop_constraint("ck_requisicion_estatus", type_="check")
        batch_op.create_check_constraint("ck_requisicion_estatus", REQUISITION_STATUS_CHECK)
        batch_op.create_index("ix_requisiciones_proyecto_id", ["proyecto_id"], unique=False)

    with op.batch_alter_table("requisiciones_detalles", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("cantidad_surtida", sa.Numeric(18, 4), nullable=False, server_default="0"))
        batch_op.create_check_constraint(
            "ck_requisicion_detalle_surtida_nonnegative",
            "cantidad_surtida >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("requisiciones_detalles", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_requisicion_detalle_surtida_nonnegative", type_="check")
        batch_op.drop_column("cantidad_surtida")

    with op.batch_alter_table("requisiciones", recreate="always") as batch_op:
        batch_op.drop_index("ix_requisiciones_proyecto_id")
        batch_op.drop_constraint("ck_requisicion_estatus", type_="check")
        batch_op.create_check_constraint(
            "ck_requisicion_estatus",
            "estatus IN ('borrador', 'enviada', 'aprobada', 'rechazada', 'surtida', 'cancelada')",
        )
        batch_op.drop_column("proyecto_nombre_snapshot")
        batch_op.drop_column("proyecto_id")
        batch_op.drop_column("es_proyecto")
