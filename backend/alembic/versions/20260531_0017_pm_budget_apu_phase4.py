"""PM budgets, budget items and basic APU phase 4.

Revision ID: 20260531_0017
Revises: 20260530_0016
Create Date: 2026-05-31 09:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260531_0017"
down_revision: str | None = "20260530_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def has_index(table_name: str, index_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def create_index_if_missing(index_name: str, table_name: str, columns: list[str], **kwargs) -> None:
    if not has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, **kwargs)


def add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not has_column(table_name, column.name):
        op.add_column(table_name, column)


def upgrade() -> None:
    if not has_table("pm_presupuestos"):
        op.create_table(
            "pm_presupuestos",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("nombre", sa.String(length=180), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("estatus", sa.String(length=20), nullable=False, server_default="borrador"),
            sa.Column("moneda", sa.String(length=8), nullable=False, server_default="MXN"),
            sa.Column("subtotal_costo", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("subtotal_venta", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("indirectos_pct", sa.Numeric(8, 4), nullable=False, server_default="0"),
            sa.Column("indirectos_monto", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("utilidad_pct", sa.Numeric(8, 4), nullable=False, server_default="0"),
            sa.Column("utilidad_monto", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("total_costo", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("total_venta", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("margen_estimado", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("notas", sa.Text(), nullable=True),
            sa.Column("aprobado_por", sa.String(length=36), nullable=True),
            sa.Column("aprobado_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["aprobado_por"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing("ix_pm_presupuestos_empresa_id", "pm_presupuestos", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_presupuestos_proyecto_id", "pm_presupuestos", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_presupuestos_estatus", "pm_presupuestos", ["estatus"], unique=False)
    create_index_if_missing("ix_pm_presupuestos_activo", "pm_presupuestos", ["activo"], unique=False)

    if not has_table("pm_presupuesto_partidas"):
        op.create_table(
            "pm_presupuesto_partidas",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("presupuesto_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("parent_id", sa.String(length=36), nullable=True),
            sa.Column("codigo", sa.String(length=60), nullable=True),
            sa.Column("nombre", sa.String(length=180), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("tipo", sa.String(length=20), nullable=False, server_default="partida"),
            sa.Column("unidad", sa.String(length=40), nullable=True),
            sa.Column("cantidad", sa.Numeric(18, 4), nullable=False, server_default="1"),
            sa.Column("costo_unitario", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("precio_unitario", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("precio_unitario_manual", sa.Numeric(18, 4), nullable=True),
            sa.Column("subtotal_costo", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("subtotal_venta", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("margen_pct", sa.Numeric(8, 4), nullable=False, server_default="0"),
            sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["presupuesto_id"], ["pm_presupuestos.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["parent_id"], ["pm_presupuesto_partidas.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing("ix_pm_presupuesto_partidas_empresa_id", "pm_presupuesto_partidas", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_partidas_presupuesto_id", "pm_presupuesto_partidas", ["presupuesto_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_partidas_proyecto_id", "pm_presupuesto_partidas", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_partidas_parent_id", "pm_presupuesto_partidas", ["parent_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_partidas_activo", "pm_presupuesto_partidas", ["activo"], unique=False)

    if not has_table("pm_presupuesto_partida_materiales"):
        op.create_table(
            "pm_presupuesto_partida_materiales",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("partida_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("material_id", sa.String(length=36), nullable=True),
            sa.Column("material_nombre_snapshot", sa.String(length=180), nullable=False),
            sa.Column("material_sku_snapshot", sa.String(length=60), nullable=True),
            sa.Column("unidad", sa.String(length=40), nullable=True),
            sa.Column("cantidad_por_unidad", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("costo_unitario", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("costo_total", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("proveedor_nombre_snapshot", sa.String(length=180), nullable=True),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["partida_id"], ["pm_presupuesto_partidas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["material_id"], ["materiales.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing("ix_pm_presupuesto_partida_materiales_empresa_id", "pm_presupuesto_partida_materiales", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_partida_materiales_partida_id", "pm_presupuesto_partida_materiales", ["partida_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_partida_materiales_proyecto_id", "pm_presupuesto_partida_materiales", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_partida_materiales_material_id", "pm_presupuesto_partida_materiales", ["material_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_partida_materiales_activo", "pm_presupuesto_partida_materiales", ["activo"], unique=False)

    if not has_table("pm_presupuesto_partida_mano_obra"):
        op.create_table(
            "pm_presupuesto_partida_mano_obra",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("partida_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("rol", sa.String(length=40), nullable=True),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("horas_por_unidad", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("tarifa_hora", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("costo_total", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["partida_id"], ["pm_presupuesto_partidas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing("ix_pm_presupuesto_partida_mano_obra_empresa_id", "pm_presupuesto_partida_mano_obra", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_partida_mano_obra_partida_id", "pm_presupuesto_partida_mano_obra", ["partida_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_partida_mano_obra_proyecto_id", "pm_presupuesto_partida_mano_obra", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_partida_mano_obra_activo", "pm_presupuesto_partida_mano_obra", ["activo"], unique=False)

    if not has_table("pm_presupuesto_indirectos"):
        op.create_table(
            "pm_presupuesto_indirectos",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("presupuesto_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("nombre", sa.String(length=160), nullable=False),
            sa.Column("tipo", sa.String(length=20), nullable=False, server_default="monto"),
            sa.Column("porcentaje", sa.Numeric(8, 4), nullable=True),
            sa.Column("monto", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["presupuesto_id"], ["pm_presupuestos.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing("ix_pm_presupuesto_indirectos_empresa_id", "pm_presupuesto_indirectos", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_indirectos_presupuesto_id", "pm_presupuesto_indirectos", ["presupuesto_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_indirectos_proyecto_id", "pm_presupuesto_indirectos", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_presupuesto_indirectos_activo", "pm_presupuesto_indirectos", ["activo"], unique=False)

    if has_table("pm_proyecto_costo_resumen"):
        add_column_if_missing(
            "pm_proyecto_costo_resumen",
            sa.Column("presupuesto_detallado_costo", sa.Numeric(18, 2), nullable=False, server_default="0"),
        )
        add_column_if_missing(
            "pm_proyecto_costo_resumen",
            sa.Column("presupuesto_detallado_venta", sa.Numeric(18, 2), nullable=False, server_default="0"),
        )
        add_column_if_missing(
            "pm_proyecto_costo_resumen",
            sa.Column("variacion_vs_presupuesto_detallado", sa.Numeric(18, 2), nullable=False, server_default="0"),
        )
        add_column_if_missing(
            "pm_proyecto_costo_resumen",
            sa.Column("presupuesto_origen", sa.String(length=20), nullable=False, server_default="simple"),
        )

        op.execute(
            sa.text(
                "UPDATE pm_proyecto_costo_resumen "
                "SET presupuesto_detallado_costo = COALESCE(presupuesto_detallado_costo, 0), "
                "presupuesto_detallado_venta = COALESCE(presupuesto_detallado_venta, 0), "
                "variacion_vs_presupuesto_detallado = COALESCE(variacion_vs_presupuesto_detallado, 0), "
                "presupuesto_origen = COALESCE(presupuesto_origen, 'simple')"
            )
        )


def downgrade() -> None:
    if has_table("pm_proyecto_costo_resumen"):
        bind = op.get_bind()
        dialect_name = bind.dialect.name
        columns = [
            "presupuesto_origen",
            "variacion_vs_presupuesto_detallado",
            "presupuesto_detallado_venta",
            "presupuesto_detallado_costo",
        ]
        if dialect_name == "sqlite":
            with op.batch_alter_table("pm_proyecto_costo_resumen", recreate="always") as batch_op:
                for column_name in columns:
                    if has_column("pm_proyecto_costo_resumen", column_name):
                        batch_op.drop_column(column_name)
        else:
            for column_name in columns:
                if has_column("pm_proyecto_costo_resumen", column_name):
                    op.drop_column("pm_proyecto_costo_resumen", column_name)

    if has_table("pm_presupuesto_indirectos"):
        for index_name in [
            "ix_pm_presupuesto_indirectos_activo",
            "ix_pm_presupuesto_indirectos_proyecto_id",
            "ix_pm_presupuesto_indirectos_presupuesto_id",
            "ix_pm_presupuesto_indirectos_empresa_id",
        ]:
            if has_index("pm_presupuesto_indirectos", index_name):
                op.drop_index(index_name, table_name="pm_presupuesto_indirectos")
        op.drop_table("pm_presupuesto_indirectos")

    if has_table("pm_presupuesto_partida_mano_obra"):
        for index_name in [
            "ix_pm_presupuesto_partida_mano_obra_activo",
            "ix_pm_presupuesto_partida_mano_obra_proyecto_id",
            "ix_pm_presupuesto_partida_mano_obra_partida_id",
            "ix_pm_presupuesto_partida_mano_obra_empresa_id",
        ]:
            if has_index("pm_presupuesto_partida_mano_obra", index_name):
                op.drop_index(index_name, table_name="pm_presupuesto_partida_mano_obra")
        op.drop_table("pm_presupuesto_partida_mano_obra")

    if has_table("pm_presupuesto_partida_materiales"):
        for index_name in [
            "ix_pm_presupuesto_partida_materiales_activo",
            "ix_pm_presupuesto_partida_materiales_material_id",
            "ix_pm_presupuesto_partida_materiales_proyecto_id",
            "ix_pm_presupuesto_partida_materiales_partida_id",
            "ix_pm_presupuesto_partida_materiales_empresa_id",
        ]:
            if has_index("pm_presupuesto_partida_materiales", index_name):
                op.drop_index(index_name, table_name="pm_presupuesto_partida_materiales")
        op.drop_table("pm_presupuesto_partida_materiales")

    if has_table("pm_presupuesto_partidas"):
        for index_name in [
            "ix_pm_presupuesto_partidas_activo",
            "ix_pm_presupuesto_partidas_parent_id",
            "ix_pm_presupuesto_partidas_proyecto_id",
            "ix_pm_presupuesto_partidas_presupuesto_id",
            "ix_pm_presupuesto_partidas_empresa_id",
        ]:
            if has_index("pm_presupuesto_partidas", index_name):
                op.drop_index(index_name, table_name="pm_presupuesto_partidas")
        op.drop_table("pm_presupuesto_partidas")

    if has_table("pm_presupuestos"):
        for index_name in [
            "ix_pm_presupuestos_activo",
            "ix_pm_presupuestos_estatus",
            "ix_pm_presupuestos_proyecto_id",
            "ix_pm_presupuestos_empresa_id",
        ]:
            if has_index("pm_presupuestos", index_name):
                op.drop_index(index_name, table_name="pm_presupuestos")
        op.drop_table("pm_presupuestos")
