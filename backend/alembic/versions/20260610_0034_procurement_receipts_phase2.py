"""Add procurement receipt history and purchase order traceability fields.

Revision ID: 20260610_0034
Revises: 20260610_0033
Create Date: 2026-06-10 20:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260610_0034"
down_revision: str | None = "20260610_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}

    with op.batch_alter_table("ordenes_compra", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("fecha_emitida", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("fecha_esperada", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("fecha_ultima_recepcion", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("documento_referencia", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("notas_recepcion", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("recibido_por_user_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("proveedor_contacto_snapshot", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("proveedor_email_snapshot", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("proveedor_telefono_snapshot", sa.String(length=40), nullable=True))
        batch_op.create_foreign_key(
            "fk_ordenes_compra_recibido_por_user_id",
            "usuarios",
            ["recibido_por_user_id"],
            ["id"],
        )

    op.create_index(
        "ix_ordenes_compra_recibido_por_user_id",
        "ordenes_compra",
        ["recibido_por_user_id"],
        unique=False,
    )

    with op.batch_alter_table("ordenes_compra_detalles", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("ultima_recepcion_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "ordenes_compra_recepciones",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("orden_compra_id", sa.String(length=36), nullable=False),
        sa.Column("almacen_id", sa.String(length=36), nullable=False),
        sa.Column("documento_referencia", sa.String(length=160), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("recibido_por_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["orden_compra_id"], ["ordenes_compra.id"]),
        sa.ForeignKeyConstraint(["almacen_id"], ["almacenes.id"]),
        sa.ForeignKeyConstraint(["recibido_por_user_id"], ["usuarios.id"]),
    )
    op.create_index("ix_ordenes_compra_recepciones_empresa_id", "ordenes_compra_recepciones", ["empresa_id"], unique=False)
    op.create_index("ix_ordenes_compra_recepciones_orden_compra_id", "ordenes_compra_recepciones", ["orden_compra_id"], unique=False)
    op.create_index("ix_ordenes_compra_recepciones_almacen_id", "ordenes_compra_recepciones", ["almacen_id"], unique=False)
    op.create_index(
        "ix_ordenes_compra_recepciones_recibido_por_user_id",
        "ordenes_compra_recepciones",
        ["recibido_por_user_id"],
        unique=False,
    )

    op.create_table(
        "ordenes_compra_recepcion_detalles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("recepcion_id", sa.String(length=36), nullable=False),
        sa.Column("orden_compra_detalle_id", sa.String(length=36), nullable=False),
        sa.Column("material_id", sa.String(length=36), nullable=False),
        sa.Column("cantidad_recibida", sa.Numeric(18, 4), nullable=False),
        sa.Column("costo_unitario_snapshot", sa.Numeric(18, 4), nullable=False),
        sa.Column("movimiento_inventario_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint("cantidad_recibida > 0", name="ck_orden_compra_recepcion_detalle_cantidad_positive"),
        sa.CheckConstraint(
            "costo_unitario_snapshot >= 0",
            name="ck_orden_compra_recepcion_detalle_costo_nonnegative",
        ),
        sa.ForeignKeyConstraint(["recepcion_id"], ["ordenes_compra_recepciones.id"]),
        sa.ForeignKeyConstraint(["orden_compra_detalle_id"], ["ordenes_compra_detalles.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materiales.id"]),
        sa.ForeignKeyConstraint(["movimiento_inventario_id"], ["movimientos_inventario.id"]),
    )
    op.create_index(
        "ix_ordenes_compra_recepcion_detalles_recepcion_id",
        "ordenes_compra_recepcion_detalles",
        ["recepcion_id"],
        unique=False,
    )
    op.create_index(
        "ix_ordenes_compra_recepcion_detalles_orden_compra_detalle_id",
        "ordenes_compra_recepcion_detalles",
        ["orden_compra_detalle_id"],
        unique=False,
    )
    op.create_index(
        "ix_ordenes_compra_recepcion_detalles_material_id",
        "ordenes_compra_recepcion_detalles",
        ["material_id"],
        unique=False,
    )
    op.create_index(
        "ix_ordenes_compra_recepcion_detalles_movimiento_inventario_id",
        "ordenes_compra_recepcion_detalles",
        ["movimiento_inventario_id"],
        unique=False,
    )

    op.execute(
        """
        UPDATE ordenes_compra
        SET fecha_emitida = created_at
        WHERE fecha_emitida IS NULL
          AND estatus IN ('emitida', 'recibida_parcial', 'recibida')
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ordenes_compra_recepcion_detalles_movimiento_inventario_id",
        table_name="ordenes_compra_recepcion_detalles",
    )
    op.drop_index(
        "ix_ordenes_compra_recepcion_detalles_material_id",
        table_name="ordenes_compra_recepcion_detalles",
    )
    op.drop_index(
        "ix_ordenes_compra_recepcion_detalles_orden_compra_detalle_id",
        table_name="ordenes_compra_recepcion_detalles",
    )
    op.drop_index(
        "ix_ordenes_compra_recepcion_detalles_recepcion_id",
        table_name="ordenes_compra_recepcion_detalles",
    )
    op.drop_table("ordenes_compra_recepcion_detalles")

    op.drop_index("ix_ordenes_compra_recepciones_recibido_por_user_id", table_name="ordenes_compra_recepciones")
    op.drop_index("ix_ordenes_compra_recepciones_almacen_id", table_name="ordenes_compra_recepciones")
    op.drop_index("ix_ordenes_compra_recepciones_orden_compra_id", table_name="ordenes_compra_recepciones")
    op.drop_index("ix_ordenes_compra_recepciones_empresa_id", table_name="ordenes_compra_recepciones")
    op.drop_table("ordenes_compra_recepciones")

    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("ordenes_compra_detalles", **batch_kwargs) as batch_op:
        batch_op.drop_column("ultima_recepcion_at")

    op.drop_index("ix_ordenes_compra_recibido_por_user_id", table_name="ordenes_compra")
    with op.batch_alter_table("ordenes_compra", **batch_kwargs) as batch_op:
        batch_op.drop_constraint("fk_ordenes_compra_recibido_por_user_id", type_="foreignkey")
        batch_op.drop_column("proveedor_telefono_snapshot")
        batch_op.drop_column("proveedor_email_snapshot")
        batch_op.drop_column("proveedor_contacto_snapshot")
        batch_op.drop_column("recibido_por_user_id")
        batch_op.drop_column("notas_recepcion")
        batch_op.drop_column("documento_referencia")
        batch_op.drop_column("fecha_ultima_recepcion")
        batch_op.drop_column("fecha_esperada")
        batch_op.drop_column("fecha_emitida")
