"""Add inventory phase 1.2 transfer and count tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260518_0006"
down_revision = "20260517_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transferencias_inventario",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("folio", sa.String(length=60), nullable=False),
        sa.Column("almacen_origen_id", sa.String(length=36), nullable=False),
        sa.Column("almacen_destino_id", sa.String(length=36), nullable=False),
        sa.Column("estatus", sa.String(length=20), nullable=False, server_default=sa.text("'borrador'")),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("confirmed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("cancelled_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estatus IN ('borrador', 'confirmada', 'cancelada')",
            name="ck_transferencia_inventario_estatus",
        ),
        sa.CheckConstraint(
            "almacen_origen_id <> almacen_destino_id",
            name="ck_transferencia_inventario_origen_destino_diff",
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["almacen_origen_id"], ["almacenes.id"]),
        sa.ForeignKeyConstraint(["almacen_destino_id"], ["almacenes.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["confirmed_by_user_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["cancelled_by_user_id"], ["usuarios.id"]),
        sa.UniqueConstraint("empresa_id", "folio", name="uq_transferencia_inventario_empresa_folio"),
    )
    op.create_index("ix_transferencias_inventario_empresa_id", "transferencias_inventario", ["empresa_id"], unique=False)
    op.create_index(
        "ix_transferencias_inventario_almacen_origen_id",
        "transferencias_inventario",
        ["almacen_origen_id"],
        unique=False,
    )
    op.create_index(
        "ix_transferencias_inventario_almacen_destino_id",
        "transferencias_inventario",
        ["almacen_destino_id"],
        unique=False,
    )
    op.create_index("ix_transferencias_inventario_estatus", "transferencias_inventario", ["estatus"], unique=False)
    op.create_index(
        "ix_transferencias_inventario_created_by_user_id",
        "transferencias_inventario",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_transferencias_inventario_confirmed_by_user_id",
        "transferencias_inventario",
        ["confirmed_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_transferencias_inventario_cancelled_by_user_id",
        "transferencias_inventario",
        ["cancelled_by_user_id"],
        unique=False,
    )

    op.create_table(
        "transferencias_inventario_detalles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("transferencia_id", sa.String(length=36), nullable=False),
        sa.Column("material_id", sa.String(length=36), nullable=False),
        sa.Column("cantidad", sa.Numeric(18, 4), nullable=False),
        sa.Column("costo_unitario_snapshot", sa.Numeric(18, 4), nullable=True),
        sa.CheckConstraint("cantidad > 0", name="ck_transferencia_inventario_detalle_cantidad_positive"),
        sa.CheckConstraint(
            "costo_unitario_snapshot IS NULL OR costo_unitario_snapshot >= 0",
            name="ck_transferencia_inventario_detalle_costo_nonnegative",
        ),
        sa.ForeignKeyConstraint(["transferencia_id"], ["transferencias_inventario.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materiales.id"]),
        sa.UniqueConstraint(
            "transferencia_id",
            "material_id",
            name="uq_transferencia_inventario_detalle_transferencia_material",
        ),
    )
    op.create_index(
        "ix_transferencias_inventario_detalles_transferencia_id",
        "transferencias_inventario_detalles",
        ["transferencia_id"],
        unique=False,
    )
    op.create_index(
        "ix_transferencias_inventario_detalles_material_id",
        "transferencias_inventario_detalles",
        ["material_id"],
        unique=False,
    )

    op.create_table(
        "conteos_inventario",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("almacen_id", sa.String(length=36), nullable=False),
        sa.Column("folio", sa.String(length=60), nullable=False),
        sa.Column("estatus", sa.String(length=20), nullable=False, server_default=sa.text("'borrador'")),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("applied_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("cancelled_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("estatus IN ('borrador', 'aplicado', 'cancelado')", name="ck_conteo_inventario_estatus"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["almacen_id"], ["almacenes.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["applied_by_user_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["cancelled_by_user_id"], ["usuarios.id"]),
        sa.UniqueConstraint("empresa_id", "folio", name="uq_conteo_inventario_empresa_folio"),
    )
    op.create_index("ix_conteos_inventario_empresa_id", "conteos_inventario", ["empresa_id"], unique=False)
    op.create_index("ix_conteos_inventario_almacen_id", "conteos_inventario", ["almacen_id"], unique=False)
    op.create_index("ix_conteos_inventario_estatus", "conteos_inventario", ["estatus"], unique=False)
    op.create_index(
        "ix_conteos_inventario_created_by_user_id",
        "conteos_inventario",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_conteos_inventario_applied_by_user_id",
        "conteos_inventario",
        ["applied_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_conteos_inventario_cancelled_by_user_id",
        "conteos_inventario",
        ["cancelled_by_user_id"],
        unique=False,
    )

    op.create_table(
        "conteos_inventario_detalles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("conteo_id", sa.String(length=36), nullable=False),
        sa.Column("material_id", sa.String(length=36), nullable=False),
        sa.Column("cantidad_sistema_snapshot", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("cantidad_fisica", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("diferencia", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("ajuste_movimiento_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "cantidad_sistema_snapshot >= 0",
            name="ck_conteo_inventario_detalle_sistema_nonnegative",
        ),
        sa.CheckConstraint("cantidad_fisica >= 0", name="ck_conteo_inventario_detalle_fisica_nonnegative"),
        sa.ForeignKeyConstraint(["conteo_id"], ["conteos_inventario.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materiales.id"]),
        sa.ForeignKeyConstraint(["ajuste_movimiento_id"], ["movimientos_inventario.id"]),
        sa.UniqueConstraint("conteo_id", "material_id", name="uq_conteo_inventario_detalle_conteo_material"),
    )
    op.create_index(
        "ix_conteos_inventario_detalles_conteo_id",
        "conteos_inventario_detalles",
        ["conteo_id"],
        unique=False,
    )
    op.create_index(
        "ix_conteos_inventario_detalles_material_id",
        "conteos_inventario_detalles",
        ["material_id"],
        unique=False,
    )
    op.create_index(
        "ix_conteos_inventario_detalles_ajuste_movimiento_id",
        "conteos_inventario_detalles",
        ["ajuste_movimiento_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_conteos_inventario_detalles_ajuste_movimiento_id", table_name="conteos_inventario_detalles")
    op.drop_index("ix_conteos_inventario_detalles_material_id", table_name="conteos_inventario_detalles")
    op.drop_index("ix_conteos_inventario_detalles_conteo_id", table_name="conteos_inventario_detalles")
    op.drop_table("conteos_inventario_detalles")

    op.drop_index("ix_conteos_inventario_cancelled_by_user_id", table_name="conteos_inventario")
    op.drop_index("ix_conteos_inventario_applied_by_user_id", table_name="conteos_inventario")
    op.drop_index("ix_conteos_inventario_created_by_user_id", table_name="conteos_inventario")
    op.drop_index("ix_conteos_inventario_estatus", table_name="conteos_inventario")
    op.drop_index("ix_conteos_inventario_almacen_id", table_name="conteos_inventario")
    op.drop_index("ix_conteos_inventario_empresa_id", table_name="conteos_inventario")
    op.drop_table("conteos_inventario")

    op.drop_index("ix_transferencias_inventario_detalles_material_id", table_name="transferencias_inventario_detalles")
    op.drop_index(
        "ix_transferencias_inventario_detalles_transferencia_id",
        table_name="transferencias_inventario_detalles",
    )
    op.drop_table("transferencias_inventario_detalles")

    op.drop_index("ix_transferencias_inventario_cancelled_by_user_id", table_name="transferencias_inventario")
    op.drop_index("ix_transferencias_inventario_confirmed_by_user_id", table_name="transferencias_inventario")
    op.drop_index("ix_transferencias_inventario_created_by_user_id", table_name="transferencias_inventario")
    op.drop_index("ix_transferencias_inventario_estatus", table_name="transferencias_inventario")
    op.drop_index("ix_transferencias_inventario_almacen_destino_id", table_name="transferencias_inventario")
    op.drop_index("ix_transferencias_inventario_almacen_origen_id", table_name="transferencias_inventario")
    op.drop_index("ix_transferencias_inventario_empresa_id", table_name="transferencias_inventario")
    op.drop_table("transferencias_inventario")
