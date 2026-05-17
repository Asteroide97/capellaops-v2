"""Add inventory phase 1 tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260517_0004"
down_revision = "20260515_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "almacenes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("nombre", sa.String(length=160), nullable=False),
        sa.Column("codigo", sa.String(length=60), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.UniqueConstraint("empresa_id", "codigo", name="uq_almacen_empresa_codigo"),
    )
    op.create_index(op.f("ix_almacenes_empresa_id"), "almacenes", ["empresa_id"], unique=False)

    op.create_table(
        "materiales",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=False),
        sa.Column("nombre", sa.String(length=180), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("categoria", sa.String(length=120), nullable=True),
        sa.Column("unidad", sa.String(length=40), nullable=False),
        sa.Column("costo_unitario", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("precio_venta", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("stock_minimo", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("costo_unitario >= 0", name="ck_material_costo_nonnegative"),
        sa.CheckConstraint("precio_venta >= 0", name="ck_material_precio_nonnegative"),
        sa.CheckConstraint("stock_minimo >= 0", name="ck_material_stock_minimo_nonnegative"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.UniqueConstraint("empresa_id", "sku", name="uq_material_empresa_sku"),
    )
    op.create_index(op.f("ix_materiales_empresa_id"), "materiales", ["empresa_id"], unique=False)

    op.create_table(
        "existencias",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("almacen_id", sa.String(length=36), nullable=False),
        sa.Column("material_id", sa.String(length=36), nullable=False),
        sa.Column("cantidad", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("cantidad >= 0", name="ck_existencia_cantidad_nonnegative"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["almacen_id"], ["almacenes.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materiales.id"]),
        sa.UniqueConstraint(
            "empresa_id",
            "almacen_id",
            "material_id",
            name="uq_existencia_empresa_almacen_material",
        ),
    )
    op.create_index(op.f("ix_existencias_empresa_id"), "existencias", ["empresa_id"], unique=False)
    op.create_index(op.f("ix_existencias_almacen_id"), "existencias", ["almacen_id"], unique=False)
    op.create_index(op.f("ix_existencias_material_id"), "existencias", ["material_id"], unique=False)

    op.create_table(
        "movimientos_inventario",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("almacen_id", sa.String(length=36), nullable=False),
        sa.Column("material_id", sa.String(length=36), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("cantidad", sa.Numeric(18, 4), nullable=False),
        sa.Column("cantidad_anterior", sa.Numeric(18, 4), nullable=False),
        sa.Column("cantidad_nueva", sa.Numeric(18, 4), nullable=False),
        sa.Column("referencia_tipo", sa.String(length=60), nullable=True),
        sa.Column("referencia_id", sa.String(length=64), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tipo IN ('entrada', 'salida', 'ajuste')", name="ck_movimiento_inventario_tipo"),
        sa.CheckConstraint("cantidad_nueva >= 0", name="ck_movimiento_inventario_cantidad_nueva_nonnegative"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["almacen_id"], ["almacenes.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materiales.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
    )
    op.create_index(op.f("ix_movimientos_inventario_empresa_id"), "movimientos_inventario", ["empresa_id"], unique=False)
    op.create_index(op.f("ix_movimientos_inventario_almacen_id"), "movimientos_inventario", ["almacen_id"], unique=False)
    op.create_index(op.f("ix_movimientos_inventario_material_id"), "movimientos_inventario", ["material_id"], unique=False)
    op.create_index(op.f("ix_movimientos_inventario_tipo"), "movimientos_inventario", ["tipo"], unique=False)
    op.create_index(op.f("ix_movimientos_inventario_created_by"), "movimientos_inventario", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_movimientos_inventario_created_by"), table_name="movimientos_inventario")
    op.drop_index(op.f("ix_movimientos_inventario_tipo"), table_name="movimientos_inventario")
    op.drop_index(op.f("ix_movimientos_inventario_material_id"), table_name="movimientos_inventario")
    op.drop_index(op.f("ix_movimientos_inventario_almacen_id"), table_name="movimientos_inventario")
    op.drop_index(op.f("ix_movimientos_inventario_empresa_id"), table_name="movimientos_inventario")
    op.drop_table("movimientos_inventario")

    op.drop_index(op.f("ix_existencias_material_id"), table_name="existencias")
    op.drop_index(op.f("ix_existencias_almacen_id"), table_name="existencias")
    op.drop_index(op.f("ix_existencias_empresa_id"), table_name="existencias")
    op.drop_table("existencias")

    op.drop_index(op.f("ix_materiales_empresa_id"), table_name="materiales")
    op.drop_table("materiales")

    op.drop_index(op.f("ix_almacenes_empresa_id"), table_name="almacenes")
    op.drop_table("almacenes")
