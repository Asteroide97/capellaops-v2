"""Repair PM budget lineage schema drift.

Revision ID: 20260805_0046
Revises: 20260805_0045
Create Date: 2026-08-05 15:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260805_0046"
down_revision: str | None = "20260805_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SYNC_STATUS_CHECK = "sync_status IN ('linked', 'detached', 'orphaned', 'conflict')"
ALLOWED_SYNC_STATUS = ("linked", "detached", "orphaned", "conflict")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_bind():
    return op.get_bind()


def get_inspector():
    return inspect(get_bind())


def using_sqlite() -> bool:
    return get_bind().dialect.name == "sqlite"


def batch_kwargs() -> dict[str, str]:
    return {"recreate": "always"} if using_sqlite() else {}


def has_table(table_name: str) -> bool:
    return get_inspector().has_table(table_name)


def get_columns(table_name: str) -> dict[str, dict]:
    if not has_table(table_name):
        return {}
    return {column["name"]: column for column in get_inspector().get_columns(table_name)}


def has_column(table_name: str, column_name: str) -> bool:
    return column_name in get_columns(table_name)


def get_indexes(table_name: str) -> list[dict]:
    if not has_table(table_name):
        return []
    return get_inspector().get_indexes(table_name)


def index_exists(table_name: str, index_name: str) -> bool:
    return any(index.get("name") == index_name for index in get_indexes(table_name))


def normalize_columns(columns: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(str(column).lower() for column in (columns or ()))


def unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    if not has_table(table_name):
        return False
    return any(
        constraint.get("name") == constraint_name
        for constraint in get_inspector().get_unique_constraints(table_name)
    )


def unique_columns_exist(table_name: str, columns: Sequence[str]) -> bool:
    expected = normalize_columns(columns)
    if not has_table(table_name):
        return False
    inspector = get_inspector()
    if any(normalize_columns(constraint.get("column_names")) == expected for constraint in inspector.get_unique_constraints(table_name)):
        return True
    return any(
        bool(index.get("unique")) and normalize_columns(index.get("column_names")) == expected
        for index in inspector.get_indexes(table_name)
    )


def check_constraint_exists(table_name: str, constraint_name: str) -> bool:
    if not has_table(table_name):
        return False
    try:
        constraints = get_inspector().get_check_constraints(table_name)
    except NotImplementedError:
        return False
    return any(constraint.get("name") == constraint_name for constraint in constraints)


def foreign_key_exists(
    table_name: str,
    *,
    constrained_columns: Sequence[str],
    referred_table: str,
    referred_columns: Sequence[str] | None = None,
) -> bool:
    if not has_table(table_name):
        return False
    expected_local = normalize_columns(constrained_columns)
    expected_remote = normalize_columns(referred_columns)
    for foreign_key in get_inspector().get_foreign_keys(table_name):
        if normalize_columns(foreign_key.get("constrained_columns")) != expected_local:
            continue
        if foreign_key.get("referred_table") != referred_table:
            continue
        if referred_columns is None or normalize_columns(foreign_key.get("referred_columns")) == expected_remote:
            return True
    return False


def primary_key_columns(table_name: str) -> tuple[str, ...]:
    if not has_table(table_name):
        return ()
    constraint = get_inspector().get_pk_constraint(table_name) or {}
    return normalize_columns(constraint.get("constrained_columns"))


def create_index_if_missing(index_name: str, table_name: str, columns: list[str], **kwargs) -> None:
    if not index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, **kwargs)


def count_rows(table_name: str) -> int:
    return int(get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one())


def query_exists(sql_text: str, params: dict | None = None) -> bool:
    return get_bind().execute(sa.text(sql_text), params or {}).first() is not None


def ensure_no_duplicate_partida_lineage() -> None:
    if query_exists(
        """
        SELECT 1
        FROM pm_presupuesto_partidas
        WHERE lineage_id IS NOT NULL AND lineage_id <> ''
        GROUP BY presupuesto_id, lineage_id
        HAVING COUNT(*) > 1
        """
    ):
        raise RuntimeError(
            "No se pudo reparar pm_presupuesto_partidas porque existen lineage_id duplicados dentro del mismo presupuesto."
        )


def ensure_no_duplicate_task_link_project_lineage() -> None:
    if query_exists(
        """
        SELECT 1
        FROM pm_presupuesto_task_links
        WHERE lineage_id IS NOT NULL AND lineage_id <> ''
        GROUP BY proyecto_id, lineage_id
        HAVING COUNT(*) > 1
        """
    ):
        raise RuntimeError(
            "No se pudo reparar pm_presupuesto_task_links porque existen lineage_id duplicados dentro del mismo proyecto."
        )


def ensure_no_duplicate_task_id() -> None:
    if query_exists(
        """
        SELECT 1
        FROM pm_presupuesto_task_links
        WHERE tarea_id IS NOT NULL
        GROUP BY tarea_id
        HAVING COUNT(*) > 1
        """
    ):
        raise RuntimeError(
            "No se pudo crear el indice unico filtrado de tarea_id porque hay tareas repetidas en pm_presupuesto_task_links."
        )


def ensure_valid_sync_status_values() -> None:
    placeholders = ", ".join(f":status_{index}" for index, _ in enumerate(ALLOWED_SYNC_STATUS))
    params = {f"status_{index}": value for index, value in enumerate(ALLOWED_SYNC_STATUS)}
    if query_exists(
        f"""
        SELECT 1
        FROM pm_presupuesto_task_links
        WHERE sync_status IS NOT NULL
          AND sync_status NOT IN ({placeholders})
        """,
        params,
    ):
        raise RuntimeError(
            "No se pudo asegurar el estado de sincronizacion porque pm_presupuesto_task_links contiene valores invalidos."
        )


def backfill_partida_lineage_ids() -> None:
    bind = get_bind()
    partidas = sa.table(
        "pm_presupuesto_partidas",
        sa.column("id", sa.String(length=36)),
        sa.column("lineage_id", sa.String(length=36)),
    )
    rows = bind.execute(
        sa.select(partidas.c.id).where(
            sa.or_(partidas.c.lineage_id.is_(None), partidas.c.lineage_id == "")
        )
    ).all()
    for row in rows:
        bind.execute(
            partidas.update()
            .where(partidas.c.id == row.id)
            .values(lineage_id=str(uuid4()))
        )


def ensure_budget_partidas_lineage_schema() -> None:
    if not has_column("pm_presupuesto_partidas", "lineage_id"):
        with op.batch_alter_table("pm_presupuesto_partidas", **batch_kwargs()) as batch_op:
            batch_op.add_column(sa.Column("lineage_id", sa.String(length=36), nullable=True))

    backfill_partida_lineage_ids()

    null_count = int(
        get_bind().execute(
            sa.text(
                "SELECT COUNT(*) FROM pm_presupuesto_partidas WHERE lineage_id IS NULL OR lineage_id = ''"
            )
        ).scalar_one()
    )
    if null_count:
        raise RuntimeError("No se pudo completar lineage_id en pm_presupuesto_partidas.")

    columns = get_columns("pm_presupuesto_partidas")
    if columns.get("lineage_id", {}).get("nullable", True):
        with op.batch_alter_table("pm_presupuesto_partidas", **batch_kwargs()) as batch_op:
            batch_op.alter_column("lineage_id", existing_type=sa.String(length=36), nullable=False)

    ensure_no_duplicate_partida_lineage()

    if not unique_constraint_exists("pm_presupuesto_partidas", "uq_pm_presupuesto_partidas_presupuesto_lineage") and not unique_columns_exist(
        "pm_presupuesto_partidas",
        ["presupuesto_id", "lineage_id"],
    ):
        with op.batch_alter_table("pm_presupuesto_partidas", **batch_kwargs()) as batch_op:
            batch_op.create_unique_constraint(
                "uq_pm_presupuesto_partidas_presupuesto_lineage",
                ["presupuesto_id", "lineage_id"],
            )

    create_index_if_missing(
        "ix_pm_presupuesto_partidas_lineage_id",
        "pm_presupuesto_partidas",
        ["lineage_id"],
        unique=False,
    )


def create_task_links_table() -> None:
    op.create_table(
        "pm_presupuesto_task_links",
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("proyecto_id", sa.String(length=36), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("tarea_id", sa.String(length=36), nullable=True),
        sa.Column("source_presupuesto_id", sa.String(length=36), nullable=True),
        sa.Column("source_partida_id", sa.String(length=36), nullable=True),
        sa.Column("source_capitulo_id", sa.String(length=36), nullable=True),
        sa.Column("generated_from_budget", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("sync_status", sa.String(length=20), nullable=False, server_default=sa.text("'linked'")),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(SYNC_STATUS_CHECK, name="ck_pm_presupuesto_task_links_sync_status"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], name="fk_pm_presupuesto_task_links_empresa_id"),
        sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"], name="fk_pm_presupuesto_task_links_proyecto_id"),
        sa.ForeignKeyConstraint(["tarea_id"], ["pm_tareas.id"], name="fk_pm_presupuesto_task_links_tarea_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_presupuesto_id"],
            ["pm_presupuestos.id"],
            name="fk_pm_presupuesto_task_links_source_presupuesto_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_partida_id"],
            ["pm_presupuesto_partidas.id"],
            name="fk_pm_presupuesto_task_links_source_partida_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_capitulo_id"],
            ["pm_presupuesto_partidas.id"],
            name="fk_pm_presupuesto_task_links_source_capitulo_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pm_presupuesto_task_links"),
        sa.UniqueConstraint("proyecto_id", "lineage_id", name="uq_pm_presupuesto_task_links_proyecto_lineage"),
    )


def task_link_column(name: str) -> sa.Column:
    definitions = {
        "id": sa.Column("id", sa.String(length=36), nullable=True),
        "empresa_id": sa.Column("empresa_id", sa.String(length=36), nullable=True),
        "proyecto_id": sa.Column("proyecto_id", sa.String(length=36), nullable=True),
        "lineage_id": sa.Column("lineage_id", sa.String(length=36), nullable=True),
        "tarea_id": sa.Column("tarea_id", sa.String(length=36), nullable=True),
        "source_presupuesto_id": sa.Column("source_presupuesto_id", sa.String(length=36), nullable=True),
        "source_partida_id": sa.Column("source_partida_id", sa.String(length=36), nullable=True),
        "source_capitulo_id": sa.Column("source_capitulo_id", sa.String(length=36), nullable=True),
        "generated_from_budget": sa.Column("generated_from_budget", sa.Boolean(), nullable=True),
        "sync_status": sa.Column("sync_status", sa.String(length=20), nullable=True),
        "source_hash": sa.Column("source_hash", sa.String(length=64), nullable=True),
        "last_synced_at": sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        "created_at": sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        "updated_at": sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    }
    return definitions[name]


def ensure_task_link_columns() -> None:
    columns = get_columns("pm_presupuesto_task_links")
    missing_columns = [
        column_name
        for column_name in (
            "id",
            "empresa_id",
            "proyecto_id",
            "lineage_id",
            "tarea_id",
            "source_presupuesto_id",
            "source_partida_id",
            "source_capitulo_id",
            "generated_from_budget",
            "sync_status",
            "source_hash",
            "last_synced_at",
            "created_at",
            "updated_at",
        )
        if column_name not in columns
    ]
    if not missing_columns:
        return

    with op.batch_alter_table("pm_presupuesto_task_links", **batch_kwargs()) as batch_op:
        for column_name in missing_columns:
            batch_op.add_column(task_link_column(column_name))


def backfill_task_link_values() -> None:
    if count_rows("pm_presupuesto_task_links") == 0:
        return
    if query_exists(
        """
        SELECT 1
        FROM pm_presupuesto_task_links
        WHERE id IS NULL OR id = ''
        """
    ):
        raise RuntimeError(
            "No se pudo reparar pm_presupuesto_task_links porque existen registros sin id y no es seguro generar IDs unicos fila por fila."
        )

    bind = get_bind()
    task_links = sa.table(
        "pm_presupuesto_task_links",
        sa.column("id", sa.String(length=36)),
        sa.column("empresa_id", sa.String(length=36)),
        sa.column("proyecto_id", sa.String(length=36)),
        sa.column("lineage_id", sa.String(length=36)),
        sa.column("generated_from_budget", sa.Boolean()),
        sa.column("sync_status", sa.String(length=20)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    rows = bind.execute(
        sa.select(
            task_links.c.id,
            task_links.c.empresa_id,
            task_links.c.proyecto_id,
            task_links.c.lineage_id,
            task_links.c.generated_from_budget,
            task_links.c.sync_status,
            task_links.c.created_at,
            task_links.c.updated_at,
        )
    ).mappings().all()
    for row in rows:
        values: dict[str, object] = {}
        if not row["id"]:
            values["id"] = str(uuid4())
        if not row["lineage_id"]:
            values["lineage_id"] = str(uuid4())
        if row["generated_from_budget"] is None:
            values["generated_from_budget"] = False
        if not row["sync_status"]:
            values["sync_status"] = "linked"
        if row["created_at"] is None:
            values["created_at"] = utcnow()
        if row["updated_at"] is None:
            values["updated_at"] = row["created_at"] or utcnow()
        if values:
            bind.execute(
                task_links.update()
                .where(task_links.c.id == row["id"])
                .values(**values)
            )


def ensure_task_link_required_values() -> None:
    if count_rows("pm_presupuesto_task_links") == 0:
        return
    if query_exists(
        """
        SELECT 1
        FROM pm_presupuesto_task_links
        WHERE empresa_id IS NULL OR proyecto_id IS NULL
        """
    ):
        raise RuntimeError(
            "No se pudo reparar pm_presupuesto_task_links porque faltan empresa_id o proyecto_id en registros existentes."
        )


def ensure_task_link_structure() -> None:
    if not has_table("pm_presupuesto_task_links"):
        create_task_links_table()

    ensure_task_link_columns()
    backfill_task_link_values()
    ensure_task_link_required_values()
    ensure_valid_sync_status_values()
    ensure_no_duplicate_task_link_project_lineage()
    ensure_no_duplicate_task_id()

    columns = get_columns("pm_presupuesto_task_links")
    needs_batch = False

    required_non_null_columns = {
        "id": sa.String(length=36),
        "empresa_id": sa.String(length=36),
        "proyecto_id": sa.String(length=36),
        "lineage_id": sa.String(length=36),
        "generated_from_budget": sa.Boolean(),
        "sync_status": sa.String(length=20),
        "created_at": sa.DateTime(timezone=True),
        "updated_at": sa.DateTime(timezone=True),
    }
    for column_name, column_type in required_non_null_columns.items():
        if columns.get(column_name, {}).get("nullable", True):
            needs_batch = True
            break

    if primary_key_columns("pm_presupuesto_task_links") != ("id",):
        needs_batch = True
    if not unique_constraint_exists("pm_presupuesto_task_links", "uq_pm_presupuesto_task_links_proyecto_lineage") and not unique_columns_exist(
        "pm_presupuesto_task_links",
        ["proyecto_id", "lineage_id"],
    ):
        needs_batch = True
    if not check_constraint_exists("pm_presupuesto_task_links", "ck_pm_presupuesto_task_links_sync_status"):
        needs_batch = True

    foreign_keys_to_ensure = [
        ("fk_pm_presupuesto_task_links_empresa_id", ["empresa_id"], "empresas", ["id"], None),
        ("fk_pm_presupuesto_task_links_proyecto_id", ["proyecto_id"], "pm_proyectos", ["id"], None),
        ("fk_pm_presupuesto_task_links_tarea_id", ["tarea_id"], "pm_tareas", ["id"], "SET NULL"),
        ("fk_pm_presupuesto_task_links_source_presupuesto_id", ["source_presupuesto_id"], "pm_presupuestos", ["id"], "SET NULL"),
        ("fk_pm_presupuesto_task_links_source_partida_id", ["source_partida_id"], "pm_presupuesto_partidas", ["id"], "SET NULL"),
        ("fk_pm_presupuesto_task_links_source_capitulo_id", ["source_capitulo_id"], "pm_presupuesto_partidas", ["id"], "SET NULL"),
    ]
    for _name, local_columns, referred_table, remote_columns, _ondelete in foreign_keys_to_ensure:
        if not foreign_key_exists(
            "pm_presupuesto_task_links",
            constrained_columns=local_columns,
            referred_table=referred_table,
            referred_columns=remote_columns,
        ):
            needs_batch = True
            break

    if needs_batch:
        with op.batch_alter_table("pm_presupuesto_task_links", **batch_kwargs()) as batch_op:
            for column_name, column_type in required_non_null_columns.items():
                if columns.get(column_name, {}).get("nullable", True):
                    batch_op.alter_column(column_name, existing_type=column_type, nullable=False)

            if primary_key_columns("pm_presupuesto_task_links") != ("id",):
                batch_op.create_primary_key("pk_pm_presupuesto_task_links", ["id"])

            if not unique_constraint_exists("pm_presupuesto_task_links", "uq_pm_presupuesto_task_links_proyecto_lineage") and not unique_columns_exist(
                "pm_presupuesto_task_links",
                ["proyecto_id", "lineage_id"],
            ):
                batch_op.create_unique_constraint(
                    "uq_pm_presupuesto_task_links_proyecto_lineage",
                    ["proyecto_id", "lineage_id"],
                )

            if not check_constraint_exists("pm_presupuesto_task_links", "ck_pm_presupuesto_task_links_sync_status"):
                batch_op.create_check_constraint(
                    "ck_pm_presupuesto_task_links_sync_status",
                    SYNC_STATUS_CHECK,
                )

            for name, local_columns, referred_table, remote_columns, ondelete in foreign_keys_to_ensure:
                if foreign_key_exists(
                    "pm_presupuesto_task_links",
                    constrained_columns=local_columns,
                    referred_table=referred_table,
                    referred_columns=remote_columns,
                ):
                    continue
                batch_op.create_foreign_key(
                    name,
                    referred_table,
                    local_columns,
                    remote_columns,
                    ondelete=ondelete,
                )

    create_index_if_missing(
        "ix_pm_presupuesto_task_links_empresa_id",
        "pm_presupuesto_task_links",
        ["empresa_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_pm_presupuesto_task_links_proyecto_id",
        "pm_presupuesto_task_links",
        ["proyecto_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_pm_presupuesto_task_links_lineage_id",
        "pm_presupuesto_task_links",
        ["lineage_id"],
        unique=False,
    )
    create_index_if_missing(
        "uq_pm_presupuesto_task_links_tarea_id_not_null",
        "pm_presupuesto_task_links",
        ["tarea_id"],
        unique=True,
        sqlite_where=sa.text("tarea_id IS NOT NULL"),
        mssql_where=sa.text("tarea_id IS NOT NULL"),
    )
    create_index_if_missing(
        "ix_pm_presupuesto_task_links_source_presupuesto_id",
        "pm_presupuesto_task_links",
        ["source_presupuesto_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_pm_presupuesto_task_links_source_partida_id",
        "pm_presupuesto_task_links",
        ["source_partida_id"],
        unique=False,
    )
    create_index_if_missing(
        "ix_pm_presupuesto_task_links_sync_status",
        "pm_presupuesto_task_links",
        ["sync_status"],
        unique=False,
    )


def upgrade() -> None:
    ensure_budget_partidas_lineage_schema()
    ensure_task_link_structure()


def downgrade() -> None:
    # 0046 is intentionally non-destructive. It repairs production schema drift for objects that
    # should already exist since 0045, so downgrade must not drop lineage_id or task links.
    return None
