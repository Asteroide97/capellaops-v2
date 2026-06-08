"""Fix requisition status constraint after PM requisition bridge.

Revision ID: 20260608_0026
Revises: 20260608_0025
Create Date: 2026-06-08 18:45:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260608_0026"
down_revision: str | None = "20260608_0025"
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


def has_index(table_name: str, index_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


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


def rebuild_sqlite_requisiciones() -> None:
    op.execute(sa.text("PRAGMA foreign_keys=OFF"))
    op.execute(
        sa.text(
            f"""
CREATE TABLE requisiciones__new (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    empresa_id VARCHAR(36) NOT NULL,
    folio VARCHAR(60) NOT NULL,
    solicitante_user_id VARCHAR(36) NOT NULL,
    proveedor_sugerido_id VARCHAR(36),
    orden_compra_id VARCHAR(36),
    es_proyecto BOOLEAN NOT NULL DEFAULT '0',
    proyecto_id VARCHAR(64),
    proyecto_nombre_snapshot VARCHAR(180),
    prioridad VARCHAR(20) NOT NULL DEFAULT 'normal',
    tarea_id VARCHAR(64),
    tarea_nombre_snapshot VARCHAR(180),
    partida_id VARCHAR(64),
    partida_nombre_snapshot VARCHAR(180),
    aprobador_user_id VARCHAR(64),
    motivo_rechazo TEXT,
    submitted_at DATETIME,
    approved_at DATETIME,
    rejected_at DATETIME,
    fulfilled_at DATETIME,
    cancelled_at DATETIME,
    estatus VARCHAR(20) NOT NULL DEFAULT 'borrador',
    notas TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_requisicion_empresa_folio UNIQUE (empresa_id, folio),
    CONSTRAINT ck_requisicion_estatus CHECK ({REQUISITION_STATUS_CHECK}),
    FOREIGN KEY(empresa_id) REFERENCES empresas (id),
    FOREIGN KEY(solicitante_user_id) REFERENCES usuarios (id),
    FOREIGN KEY(proveedor_sugerido_id) REFERENCES proveedores (id),
    FOREIGN KEY(orden_compra_id) REFERENCES ordenes_compra (id)
)
"""
        )
    )
    op.execute(
        sa.text(
            """
INSERT INTO requisiciones__new (
    id, empresa_id, folio, solicitante_user_id, proveedor_sugerido_id, orden_compra_id,
    es_proyecto, proyecto_id, proyecto_nombre_snapshot, prioridad, tarea_id, tarea_nombre_snapshot,
    partida_id, partida_nombre_snapshot, aprobador_user_id, motivo_rechazo, submitted_at,
    approved_at, rejected_at, fulfilled_at, cancelled_at, estatus, notas, created_at, updated_at
)
SELECT
    id, empresa_id, folio, solicitante_user_id, proveedor_sugerido_id, orden_compra_id,
    es_proyecto, proyecto_id, proyecto_nombre_snapshot, prioridad, tarea_id, tarea_nombre_snapshot,
    partida_id, partida_nombre_snapshot, aprobador_user_id, motivo_rechazo, submitted_at,
    approved_at, rejected_at, fulfilled_at, cancelled_at, estatus, notas, created_at, updated_at
FROM requisiciones
"""
        )
    )
    op.execute(sa.text("DROP TABLE requisiciones"))
    op.execute(sa.text("ALTER TABLE requisiciones__new RENAME TO requisiciones"))
    op.execute(sa.text("PRAGMA foreign_keys=ON"))

    create_index_if_missing("ix_requisiciones_empresa_id", "requisiciones", ["empresa_id"], unique=False)
    create_index_if_missing("ix_requisiciones_folio", "requisiciones", ["folio"], unique=False)
    create_index_if_missing("ix_requisiciones_solicitante_user_id", "requisiciones", ["solicitante_user_id"], unique=False)
    create_index_if_missing("ix_requisiciones_proveedor_sugerido_id", "requisiciones", ["proveedor_sugerido_id"], unique=False)
    create_index_if_missing("ix_requisiciones_orden_compra_id", "requisiciones", ["orden_compra_id"], unique=False)
    create_index_if_missing("ix_requisiciones_estatus", "requisiciones", ["estatus"], unique=False)
    create_index_if_missing("ix_requisiciones_proyecto_id", "requisiciones", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_requisicion_prioridad", "requisiciones", ["prioridad"], unique=False)
    create_index_if_missing("ix_requisicion_tarea_id", "requisiciones", ["tarea_id"], unique=False)
    create_index_if_missing("ix_requisicion_partida_id", "requisiciones", ["partida_id"], unique=False)
    create_index_if_missing("ix_requisicion_aprobador_user_id", "requisiciones", ["aprobador_user_id"], unique=False)


def upgrade() -> None:
    if not has_table("requisiciones"):
        return

    if using_sqlite():
        rebuild_sqlite_requisiciones()
        return

    if using_mssql():
        drop_mssql_check_constraint_if_exists("requisiciones", "ck_requisicion_estatus")
        create_mssql_check_constraint_if_missing("requisiciones", "ck_requisicion_estatus", REQUISITION_STATUS_CHECK)
        return

    op.drop_constraint("ck_requisicion_estatus", "requisiciones", type_="check")
    op.create_check_constraint("ck_requisicion_estatus", "requisiciones", REQUISITION_STATUS_CHECK)


def downgrade() -> None:
    # This corrective migration only normalizes the status constraint.
    # Previous revisions are not restored because the legacy SQLite constraint was incorrect.
    return
