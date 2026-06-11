"""Add supplier commercial profile fields and purchase-order supplier snapshots.

Revision ID: 20260610_0035
Revises: 20260610_0034
Create Date: 2026-06-10 23:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260610_0035"
down_revision: str | None = "20260610_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}

    with op.batch_alter_table("proveedores", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("sitio_web", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("ciudad", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("estado", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("pais", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("codigo_postal", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("telefono_contacto", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("email_contacto", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("moneda_preferida", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("condiciones_pago", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("dias_credito", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("lead_time_dias", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("metodo_pago_preferido", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("banco", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("cuenta_bancaria", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("clabe", sa.String(length=40), nullable=True))
        batch_op.create_check_constraint("ck_proveedor_dias_credito_nonnegative", "dias_credito >= 0")
        batch_op.create_check_constraint("ck_proveedor_lead_time_nonnegative", "lead_time_dias >= 0")

    with op.batch_alter_table("ordenes_compra", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("condiciones_pago_snapshot", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("moneda_snapshot", sa.String(length=16), nullable=True))


def downgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}

    with op.batch_alter_table("ordenes_compra", **batch_kwargs) as batch_op:
        batch_op.drop_column("moneda_snapshot")
        batch_op.drop_column("condiciones_pago_snapshot")

    with op.batch_alter_table("proveedores", **batch_kwargs) as batch_op:
        batch_op.drop_constraint("ck_proveedor_lead_time_nonnegative", type_="check")
        batch_op.drop_constraint("ck_proveedor_dias_credito_nonnegative", type_="check")
        batch_op.drop_column("clabe")
        batch_op.drop_column("cuenta_bancaria")
        batch_op.drop_column("banco")
        batch_op.drop_column("metodo_pago_preferido")
        batch_op.drop_column("lead_time_dias")
        batch_op.drop_column("dias_credito")
        batch_op.drop_column("condiciones_pago")
        batch_op.drop_column("moneda_preferida")
        batch_op.drop_column("email_contacto")
        batch_op.drop_column("telefono_contacto")
        batch_op.drop_column("codigo_postal")
        batch_op.drop_column("pais")
        batch_op.drop_column("estado")
        batch_op.drop_column("ciudad")
        batch_op.drop_column("sitio_web")
