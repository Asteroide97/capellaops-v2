"""Extend requisitions for operational fulfillment flow."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260529_0014"
down_revision = "20260529_0013"
branch_labels = None
depends_on = None


REQUISITION_STATUS_CHECK = (
    "estatus IN ('borrador', 'enviada', 'aprobada', 'rechazada', 'cancelada', "
    "'parcial', 'surtida', 'convertida_a_oc')"
)
LEGACY_REQUISITION_STATUS_CHECK = "estatus IN ('borrador', 'enviada', 'aprobada', 'rechazada', 'surtida', 'cancelada')"


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def using_mssql() -> bool:
    return op.get_bind().dialect.name == "mssql"


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
    if using_sqlite():
        with op.batch_alter_table("requisiciones", recreate="always") as batch_op:
            if not has_column("requisiciones", "es_proyecto"):
                batch_op.add_column(sa.Column("es_proyecto", sa.Boolean(), nullable=False, server_default="0"))
            if not has_column("requisiciones", "proyecto_id"):
                batch_op.add_column(sa.Column("proyecto_id", sa.String(length=64), nullable=True))
            if not has_column("requisiciones", "proyecto_nombre_snapshot"):
                batch_op.add_column(sa.Column("proyecto_nombre_snapshot", sa.String(length=180), nullable=True))
            if not has_index("requisiciones", "ix_requisiciones_proyecto_id"):
                batch_op.create_index("ix_requisiciones_proyecto_id", ["proyecto_id"], unique=False)
    else:
        if not has_column("requisiciones", "es_proyecto"):
            op.add_column("requisiciones", sa.Column("es_proyecto", sa.Boolean(), nullable=False, server_default="0"))
        if not has_column("requisiciones", "proyecto_id"):
            op.add_column("requisiciones", sa.Column("proyecto_id", sa.String(length=64), nullable=True))
        if not has_column("requisiciones", "proyecto_nombre_snapshot"):
            op.add_column("requisiciones", sa.Column("proyecto_nombre_snapshot", sa.String(length=180), nullable=True))
        if not has_index("requisiciones", "ix_requisiciones_proyecto_id"):
            op.create_index("ix_requisiciones_proyecto_id", "requisiciones", ["proyecto_id"], unique=False)
        if using_mssql():
            drop_mssql_check_constraint_if_exists("requisiciones", "ck_requisicion_estatus")
            create_mssql_check_constraint_if_missing("requisiciones", "ck_requisicion_estatus", REQUISITION_STATUS_CHECK)
        else:
            if has_check_constraint("requisiciones", "ck_requisicion_estatus"):
                op.drop_constraint("ck_requisicion_estatus", "requisiciones", type_="check")
            op.create_check_constraint("ck_requisicion_estatus", "requisiciones", REQUISITION_STATUS_CHECK)

    if using_sqlite():
        with op.batch_alter_table("requisiciones_detalles", recreate="always") as batch_op:
            if not has_column("requisiciones_detalles", "cantidad_surtida"):
                batch_op.add_column(sa.Column("cantidad_surtida", sa.Numeric(18, 4), nullable=False, server_default="0"))
    else:
        if not has_column("requisiciones_detalles", "cantidad_surtida"):
            op.add_column(
                "requisiciones_detalles",
                sa.Column("cantidad_surtida", sa.Numeric(18, 4), nullable=False, server_default="0"),
            )
        if not has_check_constraint("requisiciones_detalles", "ck_requisicion_detalle_surtida_nonnegative"):
            op.create_check_constraint(
                "ck_requisicion_detalle_surtida_nonnegative",
                "requisiciones_detalles",
                "cantidad_surtida >= 0",
            )


def downgrade() -> None:
    if using_sqlite():
        with op.batch_alter_table("requisiciones_detalles", recreate="always") as batch_op:
            if has_column("requisiciones_detalles", "cantidad_surtida"):
                batch_op.drop_column("cantidad_surtida")
    else:
        if has_check_constraint("requisiciones_detalles", "ck_requisicion_detalle_surtida_nonnegative"):
            op.drop_constraint(
                "ck_requisicion_detalle_surtida_nonnegative",
                "requisiciones_detalles",
                type_="check",
            )
        if has_column("requisiciones_detalles", "cantidad_surtida"):
            op.drop_column("requisiciones_detalles", "cantidad_surtida")

    if using_sqlite():
        with op.batch_alter_table("requisiciones", recreate="always") as batch_op:
            if has_index("requisiciones", "ix_requisiciones_proyecto_id"):
                batch_op.drop_index("ix_requisiciones_proyecto_id")
            if has_column("requisiciones", "proyecto_nombre_snapshot"):
                batch_op.drop_column("proyecto_nombre_snapshot")
            if has_column("requisiciones", "proyecto_id"):
                batch_op.drop_column("proyecto_id")
            if has_column("requisiciones", "es_proyecto"):
                batch_op.drop_column("es_proyecto")
    else:
        if has_index("requisiciones", "ix_requisiciones_proyecto_id"):
            op.drop_index("ix_requisiciones_proyecto_id", table_name="requisiciones")
        if using_mssql():
            drop_mssql_check_constraint_if_exists("requisiciones", "ck_requisicion_estatus")
            create_mssql_check_constraint_if_missing("requisiciones", "ck_requisicion_estatus", LEGACY_REQUISITION_STATUS_CHECK)
        else:
            if has_check_constraint("requisiciones", "ck_requisicion_estatus"):
                op.drop_constraint("ck_requisicion_estatus", "requisiciones", type_="check")
            op.create_check_constraint("ck_requisicion_estatus", "requisiciones", LEGACY_REQUISITION_STATUS_CHECK)
        if has_column("requisiciones", "proyecto_nombre_snapshot"):
            op.drop_column("requisiciones", "proyecto_nombre_snapshot")
        if has_column("requisiciones", "proyecto_id"):
            op.drop_column("requisiciones", "proyecto_id")
        if has_column("requisiciones", "es_proyecto"):
            op.drop_column("requisiciones", "es_proyecto")
