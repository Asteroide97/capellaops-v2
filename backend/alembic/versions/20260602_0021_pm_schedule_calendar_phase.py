"""PM schedule calendar and rescheduling phase 7.

Revision ID: 20260602_0021
Revises: 20260601_0020
Create Date: 2026-06-02 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260602_0021"
down_revision: str | None = "20260601_0020"
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
    if not has_table("pm_calendarios_laborales"):
        op.create_table(
            "pm_calendarios_laborales",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=True),
            sa.Column("nombre", sa.String(length=120), nullable=False, server_default="Calendario estándar"),
            sa.Column("lunes", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("martes", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("miercoles", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("jueves", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("viernes", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("sabado", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("domingo", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    create_index_if_missing("ix_pm_calendarios_laborales_empresa_id", "pm_calendarios_laborales", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_calendarios_laborales_proyecto_id", "pm_calendarios_laborales", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_calendarios_laborales_activo", "pm_calendarios_laborales", ["activo"], unique=False)


def downgrade() -> None:
    if has_table("pm_calendarios_laborales"):
        for index_name in [
            "ix_pm_calendarios_laborales_activo",
            "ix_pm_calendarios_laborales_proyecto_id",
            "ix_pm_calendarios_laborales_empresa_id",
        ]:
            if has_index("pm_calendarios_laborales", index_name):
                op.drop_index(index_name, table_name="pm_calendarios_laborales")
        op.drop_table("pm_calendarios_laborales")
