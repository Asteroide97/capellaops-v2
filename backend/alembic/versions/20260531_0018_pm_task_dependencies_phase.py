"""PM task dependencies and prerequisites phase 4.5.

Revision ID: 20260531_0018
Revises: 20260531_0017
Create Date: 2026-05-31 16:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260531_0018"
down_revision: str | None = "20260531_0017"
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
    if not has_table("pm_tarea_dependencias"):
        op.create_table(
            "pm_tarea_dependencias",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("tarea_id", sa.String(length=36), nullable=False),
            sa.Column("depende_de_tarea_id", sa.String(length=36), nullable=False),
            sa.Column("tipo_dependencia", sa.String(length=30), nullable=False, server_default="finish_to_start"),
            sa.Column("lag_dias", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("bloqueante", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("notas", sa.Text(), nullable=True),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["tarea_id"], ["pm_tareas.id"]),
            sa.ForeignKeyConstraint(["depende_de_tarea_id"], ["pm_tareas.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    create_index_if_missing("ix_pm_tarea_dependencias_empresa_id", "pm_tarea_dependencias", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_tarea_dependencias_proyecto_id", "pm_tarea_dependencias", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_tarea_dependencias_tarea_id", "pm_tarea_dependencias", ["tarea_id"], unique=False)
    create_index_if_missing(
        "ix_pm_tarea_dependencias_depende_de_tarea_id",
        "pm_tarea_dependencias",
        ["depende_de_tarea_id"],
        unique=False,
    )
    create_index_if_missing("ix_pm_tarea_dependencias_activo", "pm_tarea_dependencias", ["activo"], unique=False)
    create_index_if_missing(
        "uq_pm_tarea_dependencia_activa",
        "pm_tarea_dependencias",
        ["empresa_id", "proyecto_id", "tarea_id", "depende_de_tarea_id"],
        unique=True,
        sqlite_where=sa.text("activo = 1"),
        mssql_where=sa.text("activo = 1"),
    )


def downgrade() -> None:
    if has_table("pm_tarea_dependencias"):
        for index_name in [
            "uq_pm_tarea_dependencia_activa",
            "ix_pm_tarea_dependencias_activo",
            "ix_pm_tarea_dependencias_depende_de_tarea_id",
            "ix_pm_tarea_dependencias_tarea_id",
            "ix_pm_tarea_dependencias_proyecto_id",
            "ix_pm_tarea_dependencias_empresa_id",
        ]:
            if has_index("pm_tarea_dependencias", index_name):
                op.drop_index(index_name, table_name="pm_tarea_dependencias")
        op.drop_table("pm_tarea_dependencias")
