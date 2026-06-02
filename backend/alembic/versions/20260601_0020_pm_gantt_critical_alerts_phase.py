"""PM gantt, critical path and alerts phase 6.

Revision ID: 20260601_0020
Revises: 20260601_0019
Create Date: 2026-06-01 16:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260601_0020"
down_revision: str | None = "20260601_0019"
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
    if not has_table("pm_alertas"):
        op.create_table(
            "pm_alertas",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("tarea_id", sa.String(length=36), nullable=True),
            sa.Column("tipo", sa.String(length=40), nullable=False),
            sa.Column("severidad", sa.String(length=20), nullable=False, server_default="warning"),
            sa.Column("titulo", sa.String(length=180), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("estatus", sa.String(length=20), nullable=False, server_default="abierta"),
            sa.Column("dedupe_key", sa.String(length=200), nullable=True),
            sa.Column("activa", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("resuelta_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resuelta_por", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["tarea_id"], ["pm_tareas.id"]),
            sa.ForeignKeyConstraint(["resuelta_por"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    create_index_if_missing("ix_pm_alertas_empresa_id", "pm_alertas", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_alertas_proyecto_id", "pm_alertas", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_alertas_tarea_id", "pm_alertas", ["tarea_id"], unique=False)
    create_index_if_missing("ix_pm_alertas_tipo", "pm_alertas", ["tipo"], unique=False)
    create_index_if_missing("ix_pm_alertas_severidad", "pm_alertas", ["severidad"], unique=False)
    create_index_if_missing("ix_pm_alertas_estatus", "pm_alertas", ["estatus"], unique=False)
    create_index_if_missing("ix_pm_alertas_activa", "pm_alertas", ["activa"], unique=False)
    create_index_if_missing("ix_pm_alertas_dedupe_key", "pm_alertas", ["dedupe_key"], unique=False)


def downgrade() -> None:
    if has_table("pm_alertas"):
        for index_name in [
            "ix_pm_alertas_dedupe_key",
            "ix_pm_alertas_activa",
            "ix_pm_alertas_estatus",
            "ix_pm_alertas_severidad",
            "ix_pm_alertas_tipo",
            "ix_pm_alertas_tarea_id",
            "ix_pm_alertas_proyecto_id",
            "ix_pm_alertas_empresa_id",
        ]:
            if has_index("pm_alertas", index_name):
                op.drop_index(index_name, table_name="pm_alertas")
        op.drop_table("pm_alertas")
