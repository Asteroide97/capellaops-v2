"""PM estimations / payment statements phase 10.

Revision ID: 20260604_0023
Revises: 20260604_0022
Create Date: 2026-06-04 16:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260604_0023"
down_revision: str | None = "20260604_0022"
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
    if not has_table("pm_estimaciones"):
        op.create_table(
            "pm_estimaciones",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("presupuesto_id", sa.String(length=36), nullable=True),
            sa.Column("linea_base_id", sa.String(length=36), nullable=True),
            sa.Column("folio", sa.String(length=80), nullable=True),
            sa.Column("nombre", sa.String(length=180), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("periodo_inicio", sa.Date(), nullable=True),
            sa.Column("periodo_fin", sa.Date(), nullable=True),
            sa.Column("estatus", sa.String(length=30), nullable=False, server_default="borrador"),
            sa.Column("moneda", sa.String(length=8), nullable=False, server_default="MXN"),
            sa.Column("monto_bruto", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("anticipo_aplicado", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("retencion_pct", sa.Numeric(8, 4), nullable=False, server_default="0"),
            sa.Column("retencion_monto", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("monto_neto", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("monto_aprobado", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("monto_cobrado", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("saldo_pendiente", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("requiere_aprobacion", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("aprobacion_id", sa.String(length=36), nullable=True),
            sa.Column("enviada_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("aprobada_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rechazada_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cobrada_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelada_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("comentario_resolucion", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["presupuesto_id"], ["pm_presupuestos.id"]),
            sa.ForeignKeyConstraint(["linea_base_id"], ["pm_proyecto_lineas_base.id"]),
            sa.ForeignKeyConstraint(["aprobacion_id"], ["pm_aprobaciones.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    create_index_if_missing("ix_pm_estimaciones_empresa_id", "pm_estimaciones", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_estimaciones_proyecto_id", "pm_estimaciones", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_estimaciones_presupuesto_id", "pm_estimaciones", ["presupuesto_id"], unique=False)
    create_index_if_missing("ix_pm_estimaciones_linea_base_id", "pm_estimaciones", ["linea_base_id"], unique=False)
    create_index_if_missing("ix_pm_estimaciones_estatus", "pm_estimaciones", ["estatus"], unique=False)
    create_index_if_missing("ix_pm_estimaciones_aprobacion_id", "pm_estimaciones", ["aprobacion_id"], unique=False)
    create_index_if_missing("ix_pm_estimaciones_activo", "pm_estimaciones", ["activo"], unique=False)

    if not has_table("pm_estimacion_detalles"):
        op.create_table(
            "pm_estimacion_detalles",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("estimacion_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("presupuesto_partida_id", sa.String(length=36), nullable=True),
            sa.Column("tarea_id", sa.String(length=36), nullable=True),
            sa.Column("codigo_snapshot", sa.String(length=60), nullable=True),
            sa.Column("concepto_snapshot", sa.String(length=180), nullable=False),
            sa.Column("unidad_snapshot", sa.String(length=40), nullable=True),
            sa.Column("cantidad_presupuestada", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("precio_unitario_snapshot", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("importe_presupuestado", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("avance_anterior_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("avance_actual_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("avance_periodo_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("importe_anterior", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("importe_periodo", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("importe_acumulado", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("saldo_por_estimar", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("notas", sa.Text(), nullable=True),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["estimacion_id"], ["pm_estimaciones.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["presupuesto_partida_id"], ["pm_presupuesto_partidas.id"]),
            sa.ForeignKeyConstraint(["tarea_id"], ["pm_tareas.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    create_index_if_missing(
        "ix_pm_estimacion_detalles_empresa_id",
        "pm_estimacion_detalles",
        ["empresa_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_pm_estimacion_detalles_estimacion_id",
        "pm_estimacion_detalles",
        ["estimacion_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_pm_estimacion_detalles_proyecto_id",
        "pm_estimacion_detalles",
        ["proyecto_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_pm_estimacion_detalles_partida_id",
        "pm_estimacion_detalles",
        ["presupuesto_partida_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_pm_estimacion_detalles_tarea_id",
        "pm_estimacion_detalles",
        ["tarea_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_pm_estimacion_detalles_activo",
        "pm_estimacion_detalles",
        ["activo"],
        unique=False,
    )


def downgrade() -> None:
    if has_table("pm_estimacion_detalles"):
        for index_name in [
            "ix_pm_estimacion_detalles_activo",
            "ix_pm_estimacion_detalles_tarea_id",
            "ix_pm_estimacion_detalles_partida_id",
            "ix_pm_estimacion_detalles_proyecto_id",
            "ix_pm_estimacion_detalles_estimacion_id",
            "ix_pm_estimacion_detalles_empresa_id",
        ]:
            if has_index("pm_estimacion_detalles", index_name):
                op.drop_index(index_name, table_name="pm_estimacion_detalles")
        op.drop_table("pm_estimacion_detalles")

    if has_table("pm_estimaciones"):
        for index_name in [
            "ix_pm_estimaciones_activo",
            "ix_pm_estimaciones_aprobacion_id",
            "ix_pm_estimaciones_estatus",
            "ix_pm_estimaciones_linea_base_id",
            "ix_pm_estimaciones_presupuesto_id",
            "ix_pm_estimaciones_proyecto_id",
            "ix_pm_estimaciones_empresa_id",
        ]:
            if has_index("pm_estimaciones", index_name):
                op.drop_index(index_name, table_name="pm_estimaciones")
        op.drop_table("pm_estimaciones")
