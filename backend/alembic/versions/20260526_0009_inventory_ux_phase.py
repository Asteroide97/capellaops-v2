"""Add inventory UX phase fields for materials, movements, and suppliers."""

from alembic import op
import sqlalchemy as sa


revision = "20260526_0009"
down_revision = "20260518_0008"
branch_labels = None
depends_on = None


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade_materiales() -> None:
    if using_sqlite():
        with op.batch_alter_table("materiales", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("subcategoria", sa.String(length=120), nullable=True))
            batch_op.add_column(sa.Column("imagen_url", sa.String(length=1000), nullable=True))
            batch_op.add_column(sa.Column("imagenes_extra_json", sa.Text(), nullable=True))
            batch_op.add_column(sa.Column("codigo_barras", sa.String(length=120), nullable=True))
            batch_op.add_column(sa.Column("costo_promedio_actual", sa.Numeric(18, 4), nullable=True))
            batch_op.add_column(sa.Column("stock_maximo", sa.Numeric(18, 4), nullable=False, server_default="0"))
            batch_op.add_column(sa.Column("ubicacion_texto", sa.String(length=255), nullable=True))
            batch_op.add_column(sa.Column("proveedor_principal_id", sa.String(length=36), nullable=True))
            batch_op.add_column(sa.Column("lead_time_dias", sa.Integer(), nullable=False, server_default="0"))
            batch_op.create_index("ix_materiales_codigo_barras", ["codigo_barras"], unique=False)
            batch_op.create_index("ix_materiales_proveedor_principal_id", ["proveedor_principal_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_materiales_proveedor_principal_id",
                "proveedores",
                ["proveedor_principal_id"],
                ["id"],
            )
            batch_op.create_check_constraint("ck_material_stock_maximo_nonnegative", "stock_maximo >= 0")
            batch_op.create_check_constraint("ck_material_lead_time_nonnegative", "lead_time_dias >= 0")
            batch_op.create_check_constraint(
                "ck_material_costo_promedio_nonnegative",
                "costo_promedio_actual IS NULL OR costo_promedio_actual >= 0",
            )
        return

    op.add_column("materiales", sa.Column("subcategoria", sa.String(length=120), nullable=True))
    op.add_column("materiales", sa.Column("imagen_url", sa.String(length=1000), nullable=True))
    op.add_column("materiales", sa.Column("imagenes_extra_json", sa.Text(), nullable=True))
    op.add_column("materiales", sa.Column("codigo_barras", sa.String(length=120), nullable=True))
    op.add_column("materiales", sa.Column("costo_promedio_actual", sa.Numeric(18, 4), nullable=True))
    op.add_column("materiales", sa.Column("stock_maximo", sa.Numeric(18, 4), nullable=False, server_default="0"))
    op.add_column("materiales", sa.Column("ubicacion_texto", sa.String(length=255), nullable=True))
    op.add_column("materiales", sa.Column("proveedor_principal_id", sa.String(length=36), nullable=True))
    op.add_column("materiales", sa.Column("lead_time_dias", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_materiales_codigo_barras", "materiales", ["codigo_barras"], unique=False)
    op.create_index("ix_materiales_proveedor_principal_id", "materiales", ["proveedor_principal_id"], unique=False)
    op.create_foreign_key(
        "fk_materiales_proveedor_principal_id",
        "materiales",
        "proveedores",
        ["proveedor_principal_id"],
        ["id"],
    )
    op.create_check_constraint("ck_material_stock_maximo_nonnegative", "materiales", "stock_maximo >= 0")
    op.create_check_constraint("ck_material_lead_time_nonnegative", "materiales", "lead_time_dias >= 0")
    op.create_check_constraint(
        "ck_material_costo_promedio_nonnegative",
        "materiales",
        "costo_promedio_actual IS NULL OR costo_promedio_actual >= 0",
    )


def upgrade_proveedores() -> None:
    if using_sqlite():
        with op.batch_alter_table("proveedores", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("razon_social", sa.String(length=200), nullable=True))
            batch_op.add_column(sa.Column("rfc", sa.String(length=40), nullable=True))
            batch_op.create_index("ix_proveedores_rfc", ["rfc"], unique=False)
        return

    op.add_column("proveedores", sa.Column("razon_social", sa.String(length=200), nullable=True))
    op.add_column("proveedores", sa.Column("rfc", sa.String(length=40), nullable=True))
    op.create_index("ix_proveedores_rfc", "proveedores", ["rfc"], unique=False)


def upgrade_movimientos() -> None:
    if using_sqlite():
        with op.batch_alter_table("movimientos_inventario", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("grupo_referencia", sa.String(length=64), nullable=True))
            batch_op.add_column(sa.Column("motivo", sa.String(length=160), nullable=True))
            batch_op.add_column(sa.Column("entregado_por", sa.String(length=160), nullable=True))
            batch_op.add_column(sa.Column("recibido_por", sa.String(length=160), nullable=True))
            batch_op.add_column(sa.Column("documento_referencia", sa.String(length=160), nullable=True))
            batch_op.add_column(sa.Column("evidencia_url", sa.String(length=1000), nullable=True))
            batch_op.add_column(
                sa.Column("estatus", sa.String(length=20), nullable=False, server_default=sa.text("'confirmado'"))
            )
            batch_op.add_column(sa.Column("es_proyecto", sa.Boolean(), nullable=False, server_default="0"))
            batch_op.add_column(sa.Column("proyecto_id", sa.String(length=64), nullable=True))
            batch_op.add_column(sa.Column("proyecto_nombre_snapshot", sa.String(length=180), nullable=True))
            batch_op.add_column(sa.Column("costo_unitario_snapshot", sa.Numeric(18, 4), nullable=True))
            batch_op.add_column(sa.Column("costo_promedio_snapshot", sa.Numeric(18, 4), nullable=True))
            batch_op.create_index("ix_movimientos_inventario_grupo_referencia", ["grupo_referencia"], unique=False)
            batch_op.create_index("ix_movimientos_inventario_estatus", ["estatus"], unique=False)
            batch_op.create_check_constraint(
                "ck_movimiento_inventario_estatus",
                "estatus IN ('borrador', 'confirmado', 'cancelado')",
            )
            batch_op.create_check_constraint(
                "ck_movimiento_inventario_costo_unitario_nonnegative",
                "costo_unitario_snapshot IS NULL OR costo_unitario_snapshot >= 0",
            )
            batch_op.create_check_constraint(
                "ck_movimiento_inventario_costo_promedio_nonnegative",
                "costo_promedio_snapshot IS NULL OR costo_promedio_snapshot >= 0",
            )
        return

    op.add_column("movimientos_inventario", sa.Column("grupo_referencia", sa.String(length=64), nullable=True))
    op.add_column("movimientos_inventario", sa.Column("motivo", sa.String(length=160), nullable=True))
    op.add_column("movimientos_inventario", sa.Column("entregado_por", sa.String(length=160), nullable=True))
    op.add_column("movimientos_inventario", sa.Column("recibido_por", sa.String(length=160), nullable=True))
    op.add_column("movimientos_inventario", sa.Column("documento_referencia", sa.String(length=160), nullable=True))
    op.add_column("movimientos_inventario", sa.Column("evidencia_url", sa.String(length=1000), nullable=True))
    op.add_column(
        "movimientos_inventario",
        sa.Column("estatus", sa.String(length=20), nullable=False, server_default=sa.text("'confirmado'")),
    )
    op.add_column("movimientos_inventario", sa.Column("es_proyecto", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("movimientos_inventario", sa.Column("proyecto_id", sa.String(length=64), nullable=True))
    op.add_column("movimientos_inventario", sa.Column("proyecto_nombre_snapshot", sa.String(length=180), nullable=True))
    op.add_column("movimientos_inventario", sa.Column("costo_unitario_snapshot", sa.Numeric(18, 4), nullable=True))
    op.add_column("movimientos_inventario", sa.Column("costo_promedio_snapshot", sa.Numeric(18, 4), nullable=True))
    op.create_index(
        "ix_movimientos_inventario_grupo_referencia",
        "movimientos_inventario",
        ["grupo_referencia"],
        unique=False,
    )
    op.create_index("ix_movimientos_inventario_estatus", "movimientos_inventario", ["estatus"], unique=False)
    op.create_check_constraint(
        "ck_movimiento_inventario_estatus",
        "movimientos_inventario",
        "estatus IN ('borrador', 'confirmado', 'cancelado')",
    )
    op.create_check_constraint(
        "ck_movimiento_inventario_costo_unitario_nonnegative",
        "movimientos_inventario",
        "costo_unitario_snapshot IS NULL OR costo_unitario_snapshot >= 0",
    )
    op.create_check_constraint(
        "ck_movimiento_inventario_costo_promedio_nonnegative",
        "movimientos_inventario",
        "costo_promedio_snapshot IS NULL OR costo_promedio_snapshot >= 0",
    )


def downgrade_movimientos() -> None:
    if using_sqlite():
        with op.batch_alter_table("movimientos_inventario", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_movimiento_inventario_costo_promedio_nonnegative", type_="check")
            batch_op.drop_constraint("ck_movimiento_inventario_costo_unitario_nonnegative", type_="check")
            batch_op.drop_constraint("ck_movimiento_inventario_estatus", type_="check")
            batch_op.drop_index("ix_movimientos_inventario_estatus")
            batch_op.drop_index("ix_movimientos_inventario_grupo_referencia")
            batch_op.drop_column("costo_promedio_snapshot")
            batch_op.drop_column("costo_unitario_snapshot")
            batch_op.drop_column("proyecto_nombre_snapshot")
            batch_op.drop_column("proyecto_id")
            batch_op.drop_column("es_proyecto")
            batch_op.drop_column("estatus")
            batch_op.drop_column("evidencia_url")
            batch_op.drop_column("documento_referencia")
            batch_op.drop_column("recibido_por")
            batch_op.drop_column("entregado_por")
            batch_op.drop_column("motivo")
            batch_op.drop_column("grupo_referencia")
        return

    op.drop_constraint("ck_movimiento_inventario_costo_promedio_nonnegative", "movimientos_inventario", type_="check")
    op.drop_constraint("ck_movimiento_inventario_costo_unitario_nonnegative", "movimientos_inventario", type_="check")
    op.drop_constraint("ck_movimiento_inventario_estatus", "movimientos_inventario", type_="check")
    op.drop_index("ix_movimientos_inventario_estatus", table_name="movimientos_inventario")
    op.drop_index("ix_movimientos_inventario_grupo_referencia", table_name="movimientos_inventario")
    op.drop_column("movimientos_inventario", "costo_promedio_snapshot")
    op.drop_column("movimientos_inventario", "costo_unitario_snapshot")
    op.drop_column("movimientos_inventario", "proyecto_nombre_snapshot")
    op.drop_column("movimientos_inventario", "proyecto_id")
    op.drop_column("movimientos_inventario", "es_proyecto")
    op.drop_column("movimientos_inventario", "estatus")
    op.drop_column("movimientos_inventario", "evidencia_url")
    op.drop_column("movimientos_inventario", "documento_referencia")
    op.drop_column("movimientos_inventario", "recibido_por")
    op.drop_column("movimientos_inventario", "entregado_por")
    op.drop_column("movimientos_inventario", "motivo")
    op.drop_column("movimientos_inventario", "grupo_referencia")


def downgrade_proveedores() -> None:
    if using_sqlite():
        with op.batch_alter_table("proveedores", recreate="always") as batch_op:
            batch_op.drop_index("ix_proveedores_rfc")
            batch_op.drop_column("rfc")
            batch_op.drop_column("razon_social")
        return

    op.drop_index("ix_proveedores_rfc", table_name="proveedores")
    op.drop_column("proveedores", "rfc")
    op.drop_column("proveedores", "razon_social")


def downgrade_materiales() -> None:
    if using_sqlite():
        with op.batch_alter_table("materiales", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_material_costo_promedio_nonnegative", type_="check")
            batch_op.drop_constraint("ck_material_lead_time_nonnegative", type_="check")
            batch_op.drop_constraint("ck_material_stock_maximo_nonnegative", type_="check")
            batch_op.drop_constraint("fk_materiales_proveedor_principal_id", type_="foreignkey")
            batch_op.drop_index("ix_materiales_proveedor_principal_id")
            batch_op.drop_index("ix_materiales_codigo_barras")
            batch_op.drop_column("lead_time_dias")
            batch_op.drop_column("proveedor_principal_id")
            batch_op.drop_column("ubicacion_texto")
            batch_op.drop_column("stock_maximo")
            batch_op.drop_column("costo_promedio_actual")
            batch_op.drop_column("codigo_barras")
            batch_op.drop_column("imagenes_extra_json")
            batch_op.drop_column("imagen_url")
            batch_op.drop_column("subcategoria")
        return

    op.drop_constraint("ck_material_costo_promedio_nonnegative", "materiales", type_="check")
    op.drop_constraint("ck_material_lead_time_nonnegative", "materiales", type_="check")
    op.drop_constraint("ck_material_stock_maximo_nonnegative", "materiales", type_="check")
    op.drop_constraint("fk_materiales_proveedor_principal_id", "materiales", type_="foreignkey")
    op.drop_index("ix_materiales_proveedor_principal_id", table_name="materiales")
    op.drop_index("ix_materiales_codigo_barras", table_name="materiales")
    op.drop_column("materiales", "lead_time_dias")
    op.drop_column("materiales", "proveedor_principal_id")
    op.drop_column("materiales", "ubicacion_texto")
    op.drop_column("materiales", "stock_maximo")
    op.drop_column("materiales", "costo_promedio_actual")
    op.drop_column("materiales", "codigo_barras")
    op.drop_column("materiales", "imagenes_extra_json")
    op.drop_column("materiales", "imagen_url")
    op.drop_column("materiales", "subcategoria")


def upgrade() -> None:
    upgrade_materiales()
    upgrade_proveedores()
    upgrade_movimientos()


def downgrade() -> None:
    downgrade_movimientos()
    downgrade_proveedores()
    downgrade_materiales()
