"""PM baseline and change control phase 8.

Revision ID: 20260604_0022
Revises: 20260602_0021
Create Date: 2026-06-04 11:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260604_0022"
down_revision: str | None = "20260602_0021"
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
    if not has_table("pm_proyecto_lineas_base"):
        op.create_table(
            "pm_proyecto_lineas_base",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("nombre", sa.String(length=180), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("estatus", sa.String(length=20), nullable=False, server_default="activa"),
            sa.Column("es_principal", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("fecha_inicio_base", sa.Date(), nullable=True),
            sa.Column("fecha_fin_base", sa.Date(), nullable=True),
            sa.Column("duracion_dias_base", sa.Integer(), nullable=True),
            sa.Column("presupuesto_base", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("costo_estimado_base", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("precio_venta_base", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("margen_base", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("porcentaje_avance_base", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("ruta_critica_json", sa.Text(), nullable=True),
            sa.Column("snapshot_json", sa.Text(), nullable=False),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    create_index_if_missing("ix_pm_lineas_base_empresa_id", "pm_proyecto_lineas_base", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_lineas_base_proyecto_id", "pm_proyecto_lineas_base", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_lineas_base_estatus", "pm_proyecto_lineas_base", ["estatus"], unique=False)
    create_index_if_missing("ix_pm_lineas_base_principal", "pm_proyecto_lineas_base", ["es_principal"], unique=False)

    if not has_table("pm_proyecto_linea_base_tareas"):
        op.create_table(
            "pm_proyecto_linea_base_tareas",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("linea_base_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("tarea_id", sa.String(length=36), nullable=True),
            sa.Column("tarea_titulo_snapshot", sa.String(length=180), nullable=False),
            sa.Column("tarea_codigo_snapshot", sa.String(length=80), nullable=True),
            sa.Column("estatus_base", sa.String(length=20), nullable=False, server_default="pendiente"),
            sa.Column("prioridad_base", sa.String(length=20), nullable=True),
            sa.Column("fecha_inicio_base", sa.Date(), nullable=True),
            sa.Column("fecha_fin_base", sa.Date(), nullable=True),
            sa.Column("duracion_dias_base", sa.Integer(), nullable=True),
            sa.Column("porcentaje_avance_base", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("estimacion_horas_base", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("es_critica_base", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("orden_base", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("activo_base", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["linea_base_id"], ["pm_proyecto_lineas_base.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["tarea_id"], ["pm_tareas.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    create_index_if_missing(
        "ix_pm_linea_base_tareas_empresa_id",
        "pm_proyecto_linea_base_tareas",
        ["empresa_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_pm_linea_base_tareas_linea_base_id",
        "pm_proyecto_linea_base_tareas",
        ["linea_base_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_pm_linea_base_tareas_proyecto_id",
        "pm_proyecto_linea_base_tareas",
        ["proyecto_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_pm_linea_base_tareas_tarea_id",
        "pm_proyecto_linea_base_tareas",
        ["tarea_id"],
        unique=False,
    )

    if not has_table("pm_cambios_proyecto"):
        op.create_table(
            "pm_cambios_proyecto",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("linea_base_id", sa.String(length=36), nullable=True),
            sa.Column("tipo_cambio", sa.String(length=40), nullable=False, server_default="otro"),
            sa.Column("titulo", sa.String(length=180), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("motivo", sa.Text(), nullable=True),
            sa.Column("estatus", sa.String(length=30), nullable=False, server_default="borrador"),
            sa.Column("requiere_aprobacion", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("aprobacion_id", sa.String(length=36), nullable=True),
            sa.Column("entidad_tipo", sa.String(length=40), nullable=True),
            sa.Column("entidad_id", sa.String(length=36), nullable=True),
            sa.Column("antes_json", sa.Text(), nullable=True),
            sa.Column("despues_json", sa.Text(), nullable=True),
            sa.Column("impacto_dias", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("impacto_costo", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("impacto_venta", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("solicitado_por", sa.String(length=36), nullable=True),
            sa.Column("solicitado_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("aprobado_por", sa.String(length=36), nullable=True),
            sa.Column("aprobado_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("aplicado_por", sa.String(length=36), nullable=True),
            sa.Column("aplicado_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["linea_base_id"], ["pm_proyecto_lineas_base.id"]),
            sa.ForeignKeyConstraint(["aprobacion_id"], ["pm_aprobaciones.id"]),
            sa.ForeignKeyConstraint(["solicitado_por"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["aprobado_por"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["aplicado_por"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    create_index_if_missing("ix_pm_cambios_empresa_id", "pm_cambios_proyecto", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_cambios_proyecto_id", "pm_cambios_proyecto", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_cambios_linea_base_id", "pm_cambios_proyecto", ["linea_base_id"], unique=False)
    create_index_if_missing("ix_pm_cambios_tipo", "pm_cambios_proyecto", ["tipo_cambio"], unique=False)
    create_index_if_missing("ix_pm_cambios_estatus", "pm_cambios_proyecto", ["estatus"], unique=False)
    create_index_if_missing("ix_pm_cambios_aprobacion_id", "pm_cambios_proyecto", ["aprobacion_id"], unique=False)


def downgrade() -> None:
    if has_table("pm_cambios_proyecto"):
        for index_name in [
            "ix_pm_cambios_aprobacion_id",
            "ix_pm_cambios_estatus",
            "ix_pm_cambios_tipo",
            "ix_pm_cambios_linea_base_id",
            "ix_pm_cambios_proyecto_id",
            "ix_pm_cambios_empresa_id",
        ]:
            if has_index("pm_cambios_proyecto", index_name):
                op.drop_index(index_name, table_name="pm_cambios_proyecto")
        op.drop_table("pm_cambios_proyecto")

    if has_table("pm_proyecto_linea_base_tareas"):
        for index_name in [
            "ix_pm_linea_base_tareas_tarea_id",
            "ix_pm_linea_base_tareas_proyecto_id",
            "ix_pm_linea_base_tareas_linea_base_id",
            "ix_pm_linea_base_tareas_empresa_id",
        ]:
            if has_index("pm_proyecto_linea_base_tareas", index_name):
                op.drop_index(index_name, table_name="pm_proyecto_linea_base_tareas")
        op.drop_table("pm_proyecto_linea_base_tareas")

    if has_table("pm_proyecto_lineas_base"):
        for index_name in [
            "ix_pm_lineas_base_principal",
            "ix_pm_lineas_base_estatus",
            "ix_pm_lineas_base_proyecto_id",
            "ix_pm_lineas_base_empresa_id",
        ]:
            if has_index("pm_proyecto_lineas_base", index_name):
                op.drop_index(index_name, table_name="pm_proyecto_lineas_base")
        op.drop_table("pm_proyecto_lineas_base")
