"""Inventory-PM bridge for project material consumption and kardex context.

Revision ID: 20260608_0024
Revises: 20260604_0023
Create Date: 2026-06-08 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260608_0024"
down_revision: str | None = "20260604_0023"
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


def upgrade() -> None:
    if not has_table("movimientos_inventario"):
        return

    with op.batch_alter_table("movimientos_inventario") as batch_op:
        if not has_column("movimientos_inventario", "pm_tarea_id"):
            batch_op.add_column(sa.Column("pm_tarea_id", sa.String(length=64), nullable=True))
        if not has_column("movimientos_inventario", "pm_tarea_nombre_snapshot"):
            batch_op.add_column(sa.Column("pm_tarea_nombre_snapshot", sa.String(length=180), nullable=True))
        if not has_column("movimientos_inventario", "pm_partida_id"):
            batch_op.add_column(sa.Column("pm_partida_id", sa.String(length=64), nullable=True))
        if not has_column("movimientos_inventario", "pm_partida_nombre_snapshot"):
            batch_op.add_column(sa.Column("pm_partida_nombre_snapshot", sa.String(length=180), nullable=True))

    create_index_if_missing(
        "ix_movimiento_inventario_proyecto_id",
        "movimientos_inventario",
        ["proyecto_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_movimiento_inventario_pm_tarea_id",
        "movimientos_inventario",
        ["pm_tarea_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_movimiento_inventario_pm_partida_id",
        "movimientos_inventario",
        ["pm_partida_id"],
        unique=False,
    )


def downgrade() -> None:
    if not has_table("movimientos_inventario"):
        return

    for index_name in [
        "ix_movimiento_inventario_pm_partida_id",
        "ix_movimiento_inventario_pm_tarea_id",
        "ix_movimiento_inventario_proyecto_id",
    ]:
        if has_index("movimientos_inventario", index_name):
            op.drop_index(index_name, table_name="movimientos_inventario")

    with op.batch_alter_table("movimientos_inventario") as batch_op:
        if has_column("movimientos_inventario", "pm_partida_nombre_snapshot"):
            batch_op.drop_column("pm_partida_nombre_snapshot")
        if has_column("movimientos_inventario", "pm_partida_id"):
            batch_op.drop_column("pm_partida_id")
        if has_column("movimientos_inventario", "pm_tarea_nombre_snapshot"):
            batch_op.drop_column("pm_tarea_nombre_snapshot")
        if has_column("movimientos_inventario", "pm_tarea_id"):
            batch_op.drop_column("pm_tarea_id")
