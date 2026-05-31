"""PM time tracking, hourly rates and labor costs phase 3

Revision ID: 20260530_0016
Revises: 20260530_0015
Create Date: 2026-05-30 00:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260530_0016"
down_revision: str | None = "20260530_0015"
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
    if has_table("empresa_pm_config") and has_column("empresa_pm_config", "pm_tiempo_enabled"):
        op.execute(
            sa.text(
                "UPDATE empresa_pm_config "
                "SET pm_tiempo_enabled = 1 "
                "WHERE pm_enabled = 1 AND (pm_tiempo_enabled IS NULL OR pm_tiempo_enabled = 0)"
            )
        )

    if not has_table("pm_time_entries"):
        op.create_table(
            "pm_time_entries",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("tarea_id", sa.String(length=36), nullable=True),
            sa.Column("usuario_id", sa.String(length=36), nullable=True),
            sa.Column("usuario_email_snapshot", sa.String(length=255), nullable=True),
            sa.Column("usuario_nombre_snapshot", sa.String(length=160), nullable=True),
            sa.Column("fecha", sa.Date(), nullable=False),
            sa.Column("horas", sa.Numeric(12, 2), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("costo_hora_aplicado_snapshot", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("costo_total_snapshot", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("fuente_tarifa", sa.String(length=20), nullable=False, server_default="sin_tarifa"),
            sa.Column("moneda", sa.String(length=8), nullable=False, server_default="MXN"),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("horas > 0", name="ck_pm_time_entries_horas_positive"),
            sa.CheckConstraint("horas <= 24", name="ck_pm_time_entries_horas_max"),
            sa.CheckConstraint(
                "costo_hora_aplicado_snapshot >= 0",
                name="ck_pm_time_entries_rate_non_negative",
            ),
            sa.CheckConstraint(
                "costo_total_snapshot >= 0",
                name="ck_pm_time_entries_total_non_negative",
            ),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["tarea_id"], ["pm_tareas.id"]),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing("ix_pm_time_entries_empresa_id", "pm_time_entries", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_time_entries_proyecto_id", "pm_time_entries", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_time_entries_tarea_id", "pm_time_entries", ["tarea_id"], unique=False)
    create_index_if_missing("ix_pm_time_entries_usuario_id", "pm_time_entries", ["usuario_id"], unique=False)
    create_index_if_missing("ix_pm_time_entries_fecha", "pm_time_entries", ["fecha"], unique=False)
    create_index_if_missing("ix_pm_time_entries_activo", "pm_time_entries", ["activo"], unique=False)

    if not has_table("pm_tarifas_hora_usuario"):
        op.create_table(
            "pm_tarifas_hora_usuario",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("usuario_id", sa.String(length=36), nullable=True),
            sa.Column("usuario_email", sa.String(length=255), nullable=False),
            sa.Column("usuario_nombre_snapshot", sa.String(length=160), nullable=True),
            sa.Column("tarifa_hora", sa.Numeric(18, 4), nullable=False),
            sa.Column("moneda", sa.String(length=8), nullable=False, server_default="MXN"),
            sa.Column("effective_from", sa.Date(), nullable=True),
            sa.Column("effective_to", sa.Date(), nullable=True),
            sa.Column("activa", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("notas", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("tarifa_hora >= 0", name="ck_pm_tarifa_usuario_non_negative"),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing("ix_pm_tarifa_usuario_empresa_id", "pm_tarifas_hora_usuario", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_tarifa_usuario_usuario_id", "pm_tarifas_hora_usuario", ["usuario_id"], unique=False)
    create_index_if_missing("ix_pm_tarifa_usuario_email", "pm_tarifas_hora_usuario", ["usuario_email"], unique=False)
    create_index_if_missing("ix_pm_tarifa_usuario_activa", "pm_tarifas_hora_usuario", ["activa"], unique=False)

    if not has_table("pm_tarifas_hora_rol"):
        op.create_table(
            "pm_tarifas_hora_rol",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("rol", sa.String(length=40), nullable=False),
            sa.Column("tarifa_hora", sa.Numeric(18, 4), nullable=False),
            sa.Column("moneda", sa.String(length=8), nullable=False, server_default="MXN"),
            sa.Column("effective_from", sa.Date(), nullable=True),
            sa.Column("effective_to", sa.Date(), nullable=True),
            sa.Column("activa", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("notas", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("tarifa_hora >= 0", name="ck_pm_tarifa_rol_non_negative"),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing("ix_pm_tarifa_rol_empresa_id", "pm_tarifas_hora_rol", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_tarifa_rol_rol", "pm_tarifas_hora_rol", ["rol"], unique=False)
    create_index_if_missing("ix_pm_tarifa_rol_activa", "pm_tarifas_hora_rol", ["activa"], unique=False)

    if has_table("pm_proyecto_costo_resumen"):
        add_column_if_missing(
            "pm_proyecto_costo_resumen",
            sa.Column("costo_horas_real", sa.Numeric(18, 2), nullable=False, server_default="0"),
        )
        add_column_if_missing(
            "pm_proyecto_costo_resumen",
            sa.Column("horas_totales", sa.Numeric(12, 2), nullable=False, server_default="0"),
        )
        add_column_if_missing(
            "pm_proyecto_costo_resumen",
            sa.Column("horas_sin_tarifa", sa.Numeric(12, 2), nullable=False, server_default="0"),
        )
        add_column_if_missing(
            "pm_proyecto_costo_resumen",
            sa.Column("costo_total_real", sa.Numeric(18, 2), nullable=False, server_default="0"),
        )
        add_column_if_missing(
            "pm_proyecto_costo_resumen",
            sa.Column("presupuesto_estimado", sa.Numeric(18, 2), nullable=False, server_default="0"),
        )
        add_column_if_missing(
            "pm_proyecto_costo_resumen",
            sa.Column("variacion_presupuesto", sa.Numeric(18, 2), nullable=False, server_default="0"),
        )
        add_column_if_missing(
            "pm_proyecto_costo_resumen",
            sa.Column("margen_estimado", sa.Numeric(18, 2), nullable=True),
        )

        op.execute(
            sa.text(
                "UPDATE pm_proyecto_costo_resumen "
                "SET costo_horas_real = COALESCE(costo_horas_real, 0), "
                "horas_totales = COALESCE(horas_totales, 0), "
                "horas_sin_tarifa = COALESCE(horas_sin_tarifa, 0), "
                "costo_total_real = COALESCE(costo_total_real, COALESCE(costo_materiales_real, 0) + COALESCE(costo_horas_real, 0)), "
                "presupuesto_estimado = COALESCE(presupuesto_estimado, 0), "
                "variacion_presupuesto = COALESCE(variacion_presupuesto, COALESCE(presupuesto_estimado, 0) - COALESCE(costo_total_real, 0))"
            )
        )


def downgrade() -> None:
    if has_table("pm_proyecto_costo_resumen"):
        bind = op.get_bind()
        dialect_name = bind.dialect.name
        if dialect_name == "sqlite":
            with op.batch_alter_table("pm_proyecto_costo_resumen", recreate="always") as batch_op:
                for column_name in [
                    "costo_horas_real",
                    "horas_totales",
                    "horas_sin_tarifa",
                    "costo_total_real",
                    "presupuesto_estimado",
                    "variacion_presupuesto",
                    "margen_estimado",
                ]:
                    if has_column("pm_proyecto_costo_resumen", column_name):
                        batch_op.drop_column(column_name)
        else:
            for column_name in [
                "margen_estimado",
                "variacion_presupuesto",
                "presupuesto_estimado",
                "costo_total_real",
                "horas_sin_tarifa",
                "horas_totales",
                "costo_horas_real",
            ]:
                if has_column("pm_proyecto_costo_resumen", column_name):
                    op.drop_column("pm_proyecto_costo_resumen", column_name)

    if has_table("pm_tarifas_hora_rol"):
        for index_name in [
            "ix_pm_tarifa_rol_activa",
            "ix_pm_tarifa_rol_rol",
            "ix_pm_tarifa_rol_empresa_id",
        ]:
            if has_index("pm_tarifas_hora_rol", index_name):
                op.drop_index(index_name, table_name="pm_tarifas_hora_rol")
        op.drop_table("pm_tarifas_hora_rol")

    if has_table("pm_tarifas_hora_usuario"):
        for index_name in [
            "ix_pm_tarifa_usuario_activa",
            "ix_pm_tarifa_usuario_email",
            "ix_pm_tarifa_usuario_usuario_id",
            "ix_pm_tarifa_usuario_empresa_id",
        ]:
            if has_index("pm_tarifas_hora_usuario", index_name):
                op.drop_index(index_name, table_name="pm_tarifas_hora_usuario")
        op.drop_table("pm_tarifas_hora_usuario")

    if has_table("pm_time_entries"):
        for index_name in [
            "ix_pm_time_entries_activo",
            "ix_pm_time_entries_fecha",
            "ix_pm_time_entries_usuario_id",
            "ix_pm_time_entries_tarea_id",
            "ix_pm_time_entries_proyecto_id",
            "ix_pm_time_entries_empresa_id",
        ]:
            if has_index("pm_time_entries", index_name):
                op.drop_index(index_name, table_name="pm_time_entries")
        op.drop_table("pm_time_entries")
