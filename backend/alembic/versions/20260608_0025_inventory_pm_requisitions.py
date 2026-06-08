"""Inventory-PM requisitions bridge fields.

Revision ID: 20260608_0025
Revises: 20260608_0024
Create Date: 2026-06-08 18:15:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260608_0025"
down_revision: str | None = "20260608_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUISITION_STATUS_CHECK = (
    "estatus IN ('borrador', 'enviada', 'aprobada', 'rechazada', 'cancelada', "
    "'parcial', 'surtida', 'convertida_a_oc')"
)


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def using_mssql() -> bool:
    return op.get_bind().dialect.name == "mssql"


def has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def has_index(table_name: str, index_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def has_check_constraint(table_name: str, constraint_name: str) -> bool:
    if using_mssql():
        bind = op.get_bind()
        result = bind.execute(
            sa.text(
                """
                SELECT 1
                FROM sys.check_constraints
                WHERE name = :constraint_name
                  AND parent_object_id = OBJECT_ID(:table_name)
                """
            ),
            {
                "constraint_name": constraint_name,
                "table_name": f"dbo.{table_name}",
            },
        ).first()
        return result is not None
    if using_sqlite():
        return False

    inspector = inspect(op.get_bind())
    try:
        return any(constraint["name"] == constraint_name for constraint in inspector.get_check_constraints(table_name))
    except NotImplementedError:
        return False


def create_index_if_missing(index_name: str, table_name: str, columns: list[str], **kwargs) -> None:
    if not has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, **kwargs)


def drop_mssql_check_constraint_if_exists(table_name: str, constraint_name: str) -> None:
    qualified_table_name = f"dbo.{table_name}"
    op.execute(
        sa.text(
            f"""
IF EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE name = '{constraint_name}'
      AND parent_object_id = OBJECT_ID('{qualified_table_name}')
)
BEGIN
    ALTER TABLE {qualified_table_name} DROP CONSTRAINT {constraint_name}
END
"""
        )
    )


def create_mssql_check_constraint_if_missing(table_name: str, constraint_name: str, condition_sql: str) -> None:
    qualified_table_name = f"dbo.{table_name}"
    op.execute(
        sa.text(
            f"""
IF NOT EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE name = '{constraint_name}'
      AND parent_object_id = OBJECT_ID('{qualified_table_name}')
)
BEGIN
    ALTER TABLE {qualified_table_name} ADD CONSTRAINT {constraint_name} CHECK ({condition_sql})
END
"""
        )
    )


def upgrade() -> None:
    if has_table("requisiciones"):
        batch_kwargs = (
            {
                "recreate": "always",
                "table_args": (sa.CheckConstraint(REQUISITION_STATUS_CHECK, name="ck_requisicion_estatus"),),
            }
            if using_sqlite()
            else {}
        )
        with op.batch_alter_table("requisiciones", **batch_kwargs) as batch_op:
            if not has_column("requisiciones", "prioridad"):
                batch_op.add_column(sa.Column("prioridad", sa.String(length=20), nullable=False, server_default="normal"))
            if not has_column("requisiciones", "tarea_id"):
                batch_op.add_column(sa.Column("tarea_id", sa.String(length=64), nullable=True))
            if not has_column("requisiciones", "tarea_nombre_snapshot"):
                batch_op.add_column(sa.Column("tarea_nombre_snapshot", sa.String(length=180), nullable=True))
            if not has_column("requisiciones", "partida_id"):
                batch_op.add_column(sa.Column("partida_id", sa.String(length=64), nullable=True))
            if not has_column("requisiciones", "partida_nombre_snapshot"):
                batch_op.add_column(sa.Column("partida_nombre_snapshot", sa.String(length=180), nullable=True))
            if not has_column("requisiciones", "aprobador_user_id"):
                batch_op.add_column(sa.Column("aprobador_user_id", sa.String(length=64), nullable=True))
            if not has_column("requisiciones", "motivo_rechazo"):
                batch_op.add_column(sa.Column("motivo_rechazo", sa.Text(), nullable=True))
            if not has_column("requisiciones", "submitted_at"):
                batch_op.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
            if not has_column("requisiciones", "approved_at"):
                batch_op.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
            if not has_column("requisiciones", "rejected_at"):
                batch_op.add_column(sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
            if not has_column("requisiciones", "fulfilled_at"):
                batch_op.add_column(sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True))
            if not has_column("requisiciones", "cancelled_at"):
                batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))

        if using_mssql():
            drop_mssql_check_constraint_if_exists("requisiciones", "ck_requisicion_estatus")
            create_mssql_check_constraint_if_missing("requisiciones", "ck_requisicion_estatus", REQUISITION_STATUS_CHECK)
        elif not using_sqlite():
            if has_check_constraint("requisiciones", "ck_requisicion_estatus"):
                op.drop_constraint("ck_requisicion_estatus", "requisiciones", type_="check")
            op.create_check_constraint("ck_requisicion_estatus", "requisiciones", REQUISITION_STATUS_CHECK)

        create_index_if_missing("ix_requisicion_prioridad", "requisiciones", ["prioridad"], unique=False)
        create_index_if_missing("ix_requisicion_tarea_id", "requisiciones", ["tarea_id"], unique=False)
        create_index_if_missing("ix_requisicion_partida_id", "requisiciones", ["partida_id"], unique=False)
        create_index_if_missing("ix_requisicion_aprobador_user_id", "requisiciones", ["aprobador_user_id"], unique=False)

    if has_table("requisiciones_detalles"):
        with op.batch_alter_table("requisiciones_detalles") as batch_op:
            if not has_column("requisiciones_detalles", "cantidad_aprobada"):
                batch_op.add_column(sa.Column("cantidad_aprobada", sa.Numeric(18, 4), nullable=True))


def downgrade() -> None:
    if has_table("requisiciones_detalles"):
        with op.batch_alter_table("requisiciones_detalles") as batch_op:
            if has_column("requisiciones_detalles", "cantidad_aprobada"):
                batch_op.drop_column("cantidad_aprobada")

    if has_table("requisiciones"):
        for index_name in [
            "ix_requisicion_aprobador_user_id",
            "ix_requisicion_partida_id",
            "ix_requisicion_tarea_id",
            "ix_requisicion_prioridad",
        ]:
            if has_index("requisiciones", index_name):
                op.drop_index(index_name, table_name="requisiciones")

        batch_kwargs = (
            {
                "recreate": "always",
                "table_args": (sa.CheckConstraint(REQUISITION_STATUS_CHECK, name="ck_requisicion_estatus"),),
            }
            if using_sqlite()
            else {}
        )
        with op.batch_alter_table("requisiciones", **batch_kwargs) as batch_op:
            if has_column("requisiciones", "cancelled_at"):
                batch_op.drop_column("cancelled_at")
            if has_column("requisiciones", "fulfilled_at"):
                batch_op.drop_column("fulfilled_at")
            if has_column("requisiciones", "rejected_at"):
                batch_op.drop_column("rejected_at")
            if has_column("requisiciones", "approved_at"):
                batch_op.drop_column("approved_at")
            if has_column("requisiciones", "submitted_at"):
                batch_op.drop_column("submitted_at")
            if has_column("requisiciones", "motivo_rechazo"):
                batch_op.drop_column("motivo_rechazo")
            if has_column("requisiciones", "aprobador_user_id"):
                batch_op.drop_column("aprobador_user_id")
            if has_column("requisiciones", "partida_nombre_snapshot"):
                batch_op.drop_column("partida_nombre_snapshot")
            if has_column("requisiciones", "partida_id"):
                batch_op.drop_column("partida_id")
            if has_column("requisiciones", "tarea_nombre_snapshot"):
                batch_op.drop_column("tarea_nombre_snapshot")
            if has_column("requisiciones", "tarea_id"):
                batch_op.drop_column("tarea_id")
            if has_column("requisiciones", "prioridad"):
                batch_op.drop_column("prioridad")
