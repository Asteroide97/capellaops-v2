"""Add POS sale payments and discount breakdown fields.

Revision ID: 20260609_0029
Revises: 20260609_0028
Create Date: 2026-06-09 22:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260609_0029"
down_revision: str | None = "20260609_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("ventas", **batch_kwargs) as batch_op:
        batch_op.add_column(
            sa.Column("descuento_lineas_total", sa.Numeric(18, 4), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("descuento_global", sa.Numeric(18, 4), nullable=False, server_default="0")
        )
        batch_op.create_check_constraint(
            "ck_venta_descuento_lineas_nonnegative",
            "descuento_lineas_total >= 0",
        )
        batch_op.create_check_constraint(
            "ck_venta_descuento_global_nonnegative",
            "descuento_global >= 0",
        )

    op.execute("UPDATE ventas SET descuento_lineas_total = COALESCE(descuento_total, 0)")
    op.execute("UPDATE ventas SET descuento_global = 0 WHERE descuento_global IS NULL")

    op.create_table(
        "ventas_pagos",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("venta_id", sa.String(length=36), nullable=False),
        sa.Column("turno_id", sa.String(length=36), nullable=True),
        sa.Column("metodo", sa.String(length=20), nullable=False),
        sa.Column("monto", sa.Numeric(18, 4), nullable=False),
        sa.Column("referencia", sa.String(length=255), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "metodo IN ('efectivo', 'tarjeta', 'transferencia', 'otro')",
            name="ck_venta_pago_metodo",
        ),
        sa.CheckConstraint("monto > 0", name="ck_venta_pago_monto_positive"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["venta_id"], ["ventas.id"]),
        sa.ForeignKeyConstraint(["turno_id"], ["pos_turnos_caja.id"]),
    )
    op.create_index("ix_ventas_pagos_empresa_id", "ventas_pagos", ["empresa_id"], unique=False)
    op.create_index("ix_ventas_pagos_venta_id", "ventas_pagos", ["venta_id"], unique=False)
    op.create_index("ix_ventas_pagos_turno_id", "ventas_pagos", ["turno_id"], unique=False)
    op.create_index("ix_ventas_pagos_metodo", "ventas_pagos", ["metodo"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ventas_pagos_metodo", table_name="ventas_pagos")
    op.drop_index("ix_ventas_pagos_turno_id", table_name="ventas_pagos")
    op.drop_index("ix_ventas_pagos_venta_id", table_name="ventas_pagos")
    op.drop_index("ix_ventas_pagos_empresa_id", table_name="ventas_pagos")
    op.drop_table("ventas_pagos")

    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("ventas", **batch_kwargs) as batch_op:
        batch_op.drop_constraint("ck_venta_descuento_global_nonnegative", type_="check")
        batch_op.drop_constraint("ck_venta_descuento_lineas_nonnegative", type_="check")
        batch_op.drop_column("descuento_global")
        batch_op.drop_column("descuento_lineas_total")
