"""Link CRM clients and contacts with POS sales, PM projects and POS invoice requests.

Revision ID: 20260616_0037
Revises: 20260611_0036
Create Date: 2026-06-16 10:15:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260616_0037"
down_revision: str | None = "20260611_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}

    with op.batch_alter_table("ventas", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("crm_cliente_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("crm_contacto_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("factura_crm_cliente_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("factura_crm_contacto_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key("fk_ventas_crm_cliente_id", "crm_clientes", ["crm_cliente_id"], ["id"])
        batch_op.create_foreign_key("fk_ventas_crm_contacto_id", "crm_contactos", ["crm_contacto_id"], ["id"])
        batch_op.create_foreign_key(
            "fk_ventas_factura_crm_cliente_id",
            "crm_clientes",
            ["factura_crm_cliente_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_ventas_factura_crm_contacto_id",
            "crm_contactos",
            ["factura_crm_contacto_id"],
            ["id"],
        )

    op.create_index("ix_ventas_crm_cliente_id", "ventas", ["crm_cliente_id"], unique=False)
    op.create_index("ix_ventas_crm_contacto_id", "ventas", ["crm_contacto_id"], unique=False)
    op.create_index("ix_ventas_factura_crm_cliente_id", "ventas", ["factura_crm_cliente_id"], unique=False)
    op.create_index("ix_ventas_factura_crm_contacto_id", "ventas", ["factura_crm_contacto_id"], unique=False)

    with op.batch_alter_table("pm_proyectos", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("crm_cliente_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("crm_contacto_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key("fk_pm_proyectos_crm_cliente_id", "crm_clientes", ["crm_cliente_id"], ["id"])
        batch_op.create_foreign_key("fk_pm_proyectos_crm_contacto_id", "crm_contactos", ["crm_contacto_id"], ["id"])

    op.create_index("ix_pm_proyectos_crm_cliente_id", "pm_proyectos", ["crm_cliente_id"], unique=False)
    op.create_index("ix_pm_proyectos_crm_contacto_id", "pm_proyectos", ["crm_contacto_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pm_proyectos_crm_contacto_id", table_name="pm_proyectos")
    op.drop_index("ix_pm_proyectos_crm_cliente_id", table_name="pm_proyectos")

    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("pm_proyectos", **batch_kwargs) as batch_op:
        batch_op.drop_constraint("fk_pm_proyectos_crm_contacto_id", type_="foreignkey")
        batch_op.drop_constraint("fk_pm_proyectos_crm_cliente_id", type_="foreignkey")
        batch_op.drop_column("crm_contacto_id")
        batch_op.drop_column("crm_cliente_id")

    op.drop_index("ix_ventas_factura_crm_contacto_id", table_name="ventas")
    op.drop_index("ix_ventas_factura_crm_cliente_id", table_name="ventas")
    op.drop_index("ix_ventas_crm_contacto_id", table_name="ventas")
    op.drop_index("ix_ventas_crm_cliente_id", table_name="ventas")

    with op.batch_alter_table("ventas", **batch_kwargs) as batch_op:
        batch_op.drop_constraint("fk_ventas_factura_crm_contacto_id", type_="foreignkey")
        batch_op.drop_constraint("fk_ventas_factura_crm_cliente_id", type_="foreignkey")
        batch_op.drop_constraint("fk_ventas_crm_contacto_id", type_="foreignkey")
        batch_op.drop_constraint("fk_ventas_crm_cliente_id", type_="foreignkey")
        batch_op.drop_column("factura_crm_contacto_id")
        batch_op.drop_column("factura_crm_cliente_id")
        batch_op.drop_column("crm_contacto_id")
        batch_op.drop_column("crm_cliente_id")
