"""PM materials, inventory consumption and real costs phase 2

Revision ID: 20260530_0015
Revises: 20260529_0014
Create Date: 2026-05-30 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260530_0015"
down_revision: str | None = "20260529_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def has_index(table_name: str, index_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def create_index_if_missing(index_name: str, table_name: str, columns: list[str], **kwargs) -> None:
    if not has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, **kwargs)


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE empresa_pm_config "
            "SET pm_materiales_enabled = 1 "
            "WHERE pm_enabled = 1 AND (pm_materiales_enabled IS NULL OR pm_materiales_enabled = 0)"
        )
    )

    if not has_table("pm_proyecto_material_plan"):
        op.create_table(
            "pm_proyecto_material_plan",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("tarea_id", sa.String(length=36), nullable=True),
            sa.Column("material_id", sa.String(length=36), nullable=False),
            sa.Column("material_nombre_snapshot", sa.String(length=180), nullable=False),
            sa.Column("material_sku_snapshot", sa.String(length=80), nullable=False),
            sa.Column("cantidad_planificada", sa.Numeric(18, 4), nullable=False),
            sa.Column("unidad", sa.String(length=40), nullable=False),
            sa.Column("costo_unitario_estimado", sa.Numeric(18, 4), nullable=True, server_default="0"),
            sa.Column("costo_total_estimado", sa.Numeric(18, 2), nullable=True, server_default="0"),
            sa.Column("estatus", sa.String(length=20), nullable=False, server_default="planeado"),
            sa.Column("observaciones", sa.Text(), nullable=True),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("cantidad_planificada > 0", name="ck_pm_material_plan_qty_positive"),
            sa.CheckConstraint(
                "costo_unitario_estimado IS NULL OR costo_unitario_estimado >= 0",
                name="ck_pm_material_plan_unit_cost_non_negative",
            ),
            sa.CheckConstraint(
                "costo_total_estimado IS NULL OR costo_total_estimado >= 0",
                name="ck_pm_material_plan_total_cost_non_negative",
            ),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["material_id"], ["materiales.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["tarea_id"], ["pm_tareas.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing("ix_pm_material_plan_empresa_id", "pm_proyecto_material_plan", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_material_plan_proyecto_id", "pm_proyecto_material_plan", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_material_plan_tarea_id", "pm_proyecto_material_plan", ["tarea_id"], unique=False)
    create_index_if_missing("ix_pm_material_plan_material_id", "pm_proyecto_material_plan", ["material_id"], unique=False)
    create_index_if_missing("ix_pm_material_plan_estatus", "pm_proyecto_material_plan", ["estatus"], unique=False)
    create_index_if_missing("ix_pm_material_plan_activo", "pm_proyecto_material_plan", ["activo"], unique=False)

    if not has_table("pm_proyecto_material_consumo"):
        op.create_table(
            "pm_proyecto_material_consumo",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("tarea_id", sa.String(length=36), nullable=True),
            sa.Column("material_id", sa.String(length=36), nullable=False),
            sa.Column("material_nombre_snapshot", sa.String(length=180), nullable=False),
            sa.Column("material_sku_snapshot", sa.String(length=80), nullable=False),
            sa.Column("movimiento_id", sa.String(length=36), nullable=True),
            sa.Column("requisicion_id", sa.String(length=36), nullable=True),
            sa.Column("requisicion_detalle_id", sa.String(length=36), nullable=True),
            sa.Column("cantidad_consumida", sa.Numeric(18, 4), nullable=False),
            sa.Column("unidad", sa.String(length=40), nullable=False),
            sa.Column("costo_unitario_snapshot", sa.Numeric(18, 4), nullable=True, server_default="0"),
            sa.Column("costo_total_snapshot", sa.Numeric(18, 2), nullable=True, server_default="0"),
            sa.Column("origen", sa.String(length=30), nullable=False, server_default="movimiento_manual"),
            sa.Column("documento_referencia", sa.String(length=120), nullable=True),
            sa.Column("notas", sa.Text(), nullable=True),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("cantidad_consumida > 0", name="ck_pm_material_consumo_qty_positive"),
            sa.CheckConstraint(
                "costo_unitario_snapshot IS NULL OR costo_unitario_snapshot >= 0",
                name="ck_pm_material_consumo_unit_cost_non_negative",
            ),
            sa.CheckConstraint(
                "costo_total_snapshot IS NULL OR costo_total_snapshot >= 0",
                name="ck_pm_material_consumo_total_cost_non_negative",
            ),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["material_id"], ["materiales.id"]),
            sa.ForeignKeyConstraint(["movimiento_id"], ["movimientos_inventario.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["requisicion_detalle_id"], ["requisiciones_detalles.id"]),
            sa.ForeignKeyConstraint(["requisicion_id"], ["requisiciones.id"]),
            sa.ForeignKeyConstraint(["tarea_id"], ["pm_tareas.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing("ix_pm_material_consumo_empresa_id", "pm_proyecto_material_consumo", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_material_consumo_proyecto_id", "pm_proyecto_material_consumo", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_material_consumo_tarea_id", "pm_proyecto_material_consumo", ["tarea_id"], unique=False)
    create_index_if_missing("ix_pm_material_consumo_material_id", "pm_proyecto_material_consumo", ["material_id"], unique=False)
    create_index_if_missing("ix_pm_material_consumo_movimiento_id", "pm_proyecto_material_consumo", ["movimiento_id"], unique=False)
    create_index_if_missing("ix_pm_material_consumo_requisicion_id", "pm_proyecto_material_consumo", ["requisicion_id"], unique=False)
    create_index_if_missing(
        "uq_pm_material_consumo_movimiento_id",
        "pm_proyecto_material_consumo",
        ["movimiento_id"],
        unique=True,
        sqlite_where=sa.text("movimiento_id IS NOT NULL"),
        mssql_where=sa.text("movimiento_id IS NOT NULL"),
    )

    if not has_table("pm_proyecto_costo_resumen"):
        op.create_table(
            "pm_proyecto_costo_resumen",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("costo_materiales_estimado", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("costo_materiales_real", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("variacion_materiales", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("total_materiales_planeados", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("total_materiales_consumidos", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing("ix_pm_costo_resumen_empresa_id", "pm_proyecto_costo_resumen", ["empresa_id"], unique=False)
    create_index_if_missing("uq_pm_costo_resumen_proyecto_id", "pm_proyecto_costo_resumen", ["proyecto_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_pm_costo_resumen_proyecto_id", table_name="pm_proyecto_costo_resumen")
    op.drop_index("ix_pm_costo_resumen_empresa_id", table_name="pm_proyecto_costo_resumen")
    op.drop_table("pm_proyecto_costo_resumen")

    op.drop_index("uq_pm_material_consumo_movimiento_id", table_name="pm_proyecto_material_consumo")
    op.drop_index("ix_pm_material_consumo_requisicion_id", table_name="pm_proyecto_material_consumo")
    op.drop_index("ix_pm_material_consumo_movimiento_id", table_name="pm_proyecto_material_consumo")
    op.drop_index("ix_pm_material_consumo_material_id", table_name="pm_proyecto_material_consumo")
    op.drop_index("ix_pm_material_consumo_tarea_id", table_name="pm_proyecto_material_consumo")
    op.drop_index("ix_pm_material_consumo_proyecto_id", table_name="pm_proyecto_material_consumo")
    op.drop_index("ix_pm_material_consumo_empresa_id", table_name="pm_proyecto_material_consumo")
    op.drop_table("pm_proyecto_material_consumo")

    op.drop_index("ix_pm_material_plan_activo", table_name="pm_proyecto_material_plan")
    op.drop_index("ix_pm_material_plan_estatus", table_name="pm_proyecto_material_plan")
    op.drop_index("ix_pm_material_plan_material_id", table_name="pm_proyecto_material_plan")
    op.drop_index("ix_pm_material_plan_tarea_id", table_name="pm_proyecto_material_plan")
    op.drop_index("ix_pm_material_plan_proyecto_id", table_name="pm_proyecto_material_plan")
    op.drop_index("ix_pm_material_plan_empresa_id", table_name="pm_proyecto_material_plan")
    op.drop_table("pm_proyecto_material_plan")

    # 0015 no modifica defaults existentes en empresa_pm_config.
