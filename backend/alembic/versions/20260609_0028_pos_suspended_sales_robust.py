"""Allow suspended POS sales and add paid_at.

Revision ID: 20260609_0028
Revises: 20260609_0027
Create Date: 2026-06-09 17:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260609_0028"
down_revision: str | None = "20260609_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("ventas", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.drop_constraint("ck_venta_estatus", type_="check")
        batch_op.create_check_constraint(
            "ck_venta_estatus",
            "estatus IN ('pagada', 'cancelada', 'suspendida')",
        )


def downgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("ventas", **batch_kwargs) as batch_op:
        batch_op.drop_constraint("ck_venta_estatus", type_="check")
        batch_op.create_check_constraint(
            "ck_venta_estatus",
            "estatus IN ('pagada', 'cancelada')",
        )
        batch_op.drop_column("paid_at")
