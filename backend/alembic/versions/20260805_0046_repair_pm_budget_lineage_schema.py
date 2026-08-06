"""Repair PM budget lineage schema drift.

Revision ID: 20260805_0046
Revises: 20260805_0045
Create Date: 2026-08-05 15:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import re
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
    # Always return a fresh Inspector after DDL so schema reads do not reuse stale reflection.
    return inspect(get_bind())


def using_mssql() -> bool:
    return get_bind().dialect.name == "mssql"


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
    try:
        return get_inspector().get_indexes(table_name)
    except (NotImplementedError, sa.exc.SQLAlchemyError):
        return []


def index_exists(table_name: str, index_name: str) -> bool:
    return any(index.get("name") == index_name for index in get_indexes(table_name))


def normalize_columns(columns: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(str(column).lower() for column in (columns or ()))


def normalize_filter_definition(filter_definition: str | None) -> str | None:
    if filter_definition is None:
        return None
    normalized = str(filter_definition).strip().lower()
    if not normalized:
        return None
    normalized = normalized.removeprefix("where ").strip()
    normalized = normalized.replace("[", "").replace("]", "")
    normalized = normalized.replace('"', "").replace("'", "")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.replace("(", "").replace(")", "")
    return normalized.strip() or None


def normalize_identifier_token(token: str) -> str:
    normalized = token.strip().lower().replace("[", "").replace("]", "").replace('"', "")
    if "." in normalized:
        normalized = normalized.split(".")[-1]
    return normalized


def normalize_check_definition(definition: str | None) -> str | None:
    if definition is None:
        return None
    normalized = str(definition).strip().lower()
    if not normalized:
        return None
    normalized = normalized.replace("[", "").replace("]", "")
    normalized = normalized.replace('"', "").replace("'", "")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = normalized.removeprefix("check ").strip()

    in_match = re.fullmatch(r"\(?([a-z0-9_\.]+)\s+in\s*\(([^)]+)\)\)?", normalized)
    if in_match:
        column_name = normalize_identifier_token(in_match.group(1))
        values = sorted(
            value.strip()
            for value in in_match.group(2).split(",")
            if value.strip()
        )
        return f"{column_name} in ({','.join(values)})"

    flat_or_expression = normalized.replace("(", "").replace(")", "")
    or_segments = [segment.strip() for segment in flat_or_expression.split(" or ") if segment.strip()]
    if or_segments:
        parsed_segments = []
        for segment in or_segments:
            match = re.fullmatch(r"([a-z0-9_\.]+)\s*=\s*([a-z0-9_]+)", segment)
            if not match:
                parsed_segments = []
                break
            parsed_segments.append((normalize_identifier_token(match.group(1)), match.group(2).strip()))
        if parsed_segments:
            first_column = parsed_segments[0][0]
            if all(column == first_column for column, _value in parsed_segments):
                values = sorted(value for _column, value in parsed_segments)
                return f"{first_column} in ({','.join(values)})"

    normalized = normalized.replace("(", "").replace(")", "")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip() or None


def first_not_none(*values):
    for value in values:
        if value is not None:
            return value
    return None


def get_inspector_unique_constraints(table_name: str) -> list[dict]:
    if not has_table(table_name):
        return []
    try:
        return get_inspector().get_unique_constraints(table_name)
    except (NotImplementedError, sa.exc.SQLAlchemyError):
        return []


def get_mssql_unique_definitions(table_name: str) -> list[dict]:
    if not using_mssql() or not has_table(table_name):
        return []
    rows = get_bind().execute(
        sa.text(
            """
            SELECT
                i.name AS object_name,
                i.is_unique AS is_unique,
                i.is_unique_constraint AS is_unique_constraint,
                i.has_filter AS has_filter,
                i.filter_definition AS filter_definition,
                ic.key_ordinal AS key_ordinal,
                c.name AS column_name
            FROM sys.tables t
            INNER JOIN sys.indexes i
                ON i.object_id = t.object_id
            INNER JOIN sys.index_columns ic
                ON ic.object_id = i.object_id
               AND ic.index_id = i.index_id
            INNER JOIN sys.columns c
                ON c.object_id = ic.object_id
               AND c.column_id = ic.column_id
            WHERE t.name = :table_name
              AND i.is_unique = 1
              AND i.is_hypothetical = 0
              AND ic.key_ordinal > 0
            ORDER BY i.name, ic.key_ordinal
            """
        ),
        {"table_name": table_name},
    ).mappings().all()
    if not rows:
        return []

    definitions_by_name: dict[str, dict] = {}
    for row in rows:
        definition = definitions_by_name.setdefault(
            row["object_name"],
            {
                "name": row["object_name"],
                "columns": [],
                "unique": bool(row["is_unique"]),
                "is_constraint": bool(row["is_unique_constraint"]),
                "filter_definition": normalize_filter_definition(row["filter_definition"])
                if row["has_filter"]
                else None,
            },
        )
        definition["columns"].append(str(row["column_name"]).lower())
    return list(definitions_by_name.values())


def get_inspector_check_constraints(table_name: str) -> list[dict]:
    if not has_table(table_name):
        return []
    try:
        return get_inspector().get_check_constraints(table_name)
    except (NotImplementedError, sa.exc.SQLAlchemyError):
        return []


def get_mssql_check_constraint_definitions(table_name: str) -> list[dict]:
    if not using_mssql() or not has_table(table_name):
        return []
    rows = get_bind().execute(
        sa.text(
            """
            SELECT
                cc.name AS constraint_name,
                cc.definition AS definition,
                t.name AS table_name,
                s.name AS schema_name
            FROM sys.check_constraints cc
            INNER JOIN sys.tables t
                ON t.object_id = cc.parent_object_id
            INNER JOIN sys.schemas s
                ON s.schema_id = t.schema_id
            WHERE t.name = :table_name
            ORDER BY cc.name
            """
        ),
        {"table_name": table_name},
    ).mappings().all()
    return [
        {
            "name": row["constraint_name"],
            "definition": row["definition"],
            "table_name": row["table_name"],
            "schema_name": row["schema_name"],
        }
        for row in rows
    ]


def get_check_constraint_definitions(table_name: str) -> list[dict]:
    if not has_table(table_name):
        return []

    definitions: list[dict] = []
    seen_signatures: set[tuple[str | None, str | None]] = set()

    for constraint in get_inspector_check_constraints(table_name):
        name = constraint.get("name")
        definition = constraint.get("sqltext")
        signature = (
            str(name).lower() if name else None,
            normalize_check_definition(definition),
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        definitions.append(
            {
                "name": name,
                "definition": definition,
                "normalized_definition": normalize_check_definition(definition),
            }
        )

    for constraint in get_mssql_check_constraint_definitions(table_name):
        name = constraint.get("name")
        definition = constraint.get("definition")
        signature = (
            str(name).lower() if name else None,
            normalize_check_definition(definition),
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        definitions.append(
            {
                "name": name,
                "definition": definition,
                "normalized_definition": normalize_check_definition(definition),
            }
        )

    return definitions


def get_unique_definitions(table_name: str) -> list[dict]:
    if not has_table(table_name):
        return []

    definitions: list[dict] = []
    seen_signatures: set[tuple[str | None, tuple[str, ...], str | None]] = set()

    for constraint in get_inspector_unique_constraints(table_name):
        if not constraint.get("name"):
            continue
        columns = normalize_columns(constraint.get("column_names"))
        signature = (str(constraint.get("name")).lower(), columns, None)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        definitions.append(
            {
                "name": constraint.get("name"),
                "columns": columns,
                "unique": True,
                "is_constraint": True,
                "filter_definition": None,
            }
        )

    for index in get_indexes(table_name):
        if not index.get("unique"):
            continue
        columns = normalize_columns(index.get("column_names"))
        filter_definition = normalize_filter_definition(
            first_not_none(
                index.get("dialect_options", {}).get("mssql_where"),
                index.get("dialect_options", {}).get("sqlite_where"),
                index.get("mssql_where"),
                index.get("sqlite_where"),
                index.get("filter_definition"),
            )
        )
        signature = (
            str(index.get("name")).lower() if index.get("name") else None,
            columns,
            filter_definition,
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        definitions.append(
            {
                "name": index.get("name"),
                "columns": columns,
                "unique": True,
                "is_constraint": False,
                "filter_definition": filter_definition,
            }
        )

    for definition in get_mssql_unique_definitions(table_name):
        signature = (
            str(definition.get("name")).lower() if definition.get("name") else None,
            normalize_columns(definition.get("columns")),
            normalize_filter_definition(definition.get("filter_definition")),
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        definitions.append(
            {
                "name": definition.get("name"),
                "columns": normalize_columns(definition.get("columns")),
                "unique": True,
                "is_constraint": bool(definition.get("is_constraint")),
                "filter_definition": normalize_filter_definition(definition.get("filter_definition")),
            }
        )

    return definitions


def unique_name_exists(table_name: str, object_name: str) -> bool:
    expected_name = str(object_name).lower()
    return any(
        str(definition.get("name")).lower() == expected_name
        for definition in get_unique_definitions(table_name)
        if definition.get("name")
    )


def unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    if not has_table(table_name):
        return False
    return unique_name_exists(table_name, constraint_name)


def unique_columns_exist(
    table_name: str,
    columns: Sequence[str],
    *,
    filter_definition: str | None = None,
) -> bool:
    expected = normalize_columns(columns)
    if not has_table(table_name):
        return False
    expected_filter = normalize_filter_definition(filter_definition)
    return any(
        definition.get("columns") == expected
        and normalize_filter_definition(definition.get("filter_definition")) == expected_filter
        for definition in get_unique_definitions(table_name)
    )


def check_constraint_name_exists(table_name: str, constraint_name: str) -> bool:
    expected_name = str(constraint_name).lower()
    return any(
        str(definition.get("name")).lower() == expected_name
        for definition in get_check_constraint_definitions(table_name)
        if definition.get("name")
    )


def equivalent_check_constraint_exists(table_name: str, expression: str) -> bool:
    expected_definition = normalize_check_definition(expression)
    return any(
        definition.get("normalized_definition") == expected_definition
        for definition in get_check_constraint_definitions(table_name)
    )


def check_constraint_exists(table_name: str, constraint_name: str, expression: str | None = None) -> bool:
    if not has_table(table_name):
        return False
    if check_constraint_name_exists(table_name, constraint_name):
        return True
    if expression is not None and equivalent_check_constraint_exists(table_name, expression):
        return True
    return False


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


def create_unique_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
    *,
    filter_definition: str | None = None,
    **kwargs,
) -> None:
    if unique_name_exists(table_name, index_name):
        return
    if unique_columns_exist(table_name, columns, filter_definition=filter_definition):
        return
    op.create_index(index_name, table_name, columns, unique=True, **kwargs)


def task_link_foreign_key_specs() -> list[dict[str, object]]:
    # Portable NO ACTION policy. Historical links stay nullable, and detach/cleanup is handled by
    # application services instead of database-level cascades so Azure SQL does not reject the DDL
    # with multiple cascade path errors.
    return [
        {
            "name": "fk_pm_presupuesto_task_links_empresa_id",
            "local_columns": ["empresa_id"],
            "referred_table": "empresas",
            "remote_columns": ["id"],
            "ondelete": None,
        },
        {
            "name": "fk_pm_presupuesto_task_links_proyecto_id",
            "local_columns": ["proyecto_id"],
            "referred_table": "pm_proyectos",
            "remote_columns": ["id"],
            "ondelete": None,
        },
        {
            "name": "fk_pm_presupuesto_task_links_tarea_id",
            "local_columns": ["tarea_id"],
            "referred_table": "pm_tareas",
            "remote_columns": ["id"],
            "ondelete": None,
        },
        {
            "name": "fk_pm_presupuesto_task_links_source_presupuesto_id",
            "local_columns": ["source_presupuesto_id"],
            "referred_table": "pm_presupuestos",
            "remote_columns": ["id"],
            "ondelete": None,
        },
        {
            "name": "fk_pm_presupuesto_task_links_source_partida_id",
            "local_columns": ["source_partida_id"],
            "referred_table": "pm_presupuesto_partidas",
            "remote_columns": ["id"],
            "ondelete": None,
        },
        {
            "name": "fk_pm_presupuesto_task_links_source_capitulo_id",
            "local_columns": ["source_capitulo_id"],
            "referred_table": "pm_presupuesto_partidas",
            "remote_columns": ["id"],
            "ondelete": None,
        },
    ]


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
    fk_specs = task_link_foreign_key_specs()
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
        *[
            sa.ForeignKeyConstraint(
                spec["local_columns"],
                [f"{spec['referred_table']}.{spec['remote_columns'][0]}"],
                name=spec["name"],
                ondelete=spec["ondelete"],
            )
            for spec in fk_specs
        ],
        sa.PrimaryKeyConstraint("id", name="pk_pm_presupuesto_task_links"),
        sa.UniqueConstraint("proyecto_id", "lineage_id", name="uq_pm_presupuesto_task_links_proyecto_lineage"),
    )


def ensure_task_link_indexes() -> None:
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
    create_unique_index_if_missing(
        "uq_pm_presupuesto_task_links_tarea_id_not_null",
        "pm_presupuesto_task_links",
        ["tarea_id"],
        filter_definition="tarea_id IS NOT NULL",
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
    table_created = False
    if not has_table("pm_presupuesto_task_links"):
        create_task_links_table()
        table_created = True

    if table_created:
        ensure_task_link_indexes()
        return

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
    if not check_constraint_exists(
        "pm_presupuesto_task_links",
        "ck_pm_presupuesto_task_links_sync_status",
        SYNC_STATUS_CHECK,
    ):
        needs_batch = True

    foreign_keys_to_ensure = task_link_foreign_key_specs()
    for spec in foreign_keys_to_ensure:
        if not foreign_key_exists(
            "pm_presupuesto_task_links",
            constrained_columns=spec["local_columns"],
            referred_table=str(spec["referred_table"]),
            referred_columns=spec["remote_columns"],
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

            if not check_constraint_exists(
                "pm_presupuesto_task_links",
                "ck_pm_presupuesto_task_links_sync_status",
                SYNC_STATUS_CHECK,
            ):
                batch_op.create_check_constraint(
                    "ck_pm_presupuesto_task_links_sync_status",
                    SYNC_STATUS_CHECK,
                )

            for spec in foreign_keys_to_ensure:
                if foreign_key_exists(
                    "pm_presupuesto_task_links",
                    constrained_columns=spec["local_columns"],
                    referred_table=str(spec["referred_table"]),
                    referred_columns=spec["remote_columns"],
                ):
                    continue
                batch_op.create_foreign_key(
                    str(spec["name"]),
                    str(spec["referred_table"]),
                    spec["local_columns"],
                    spec["remote_columns"],
                    ondelete=spec["ondelete"],
                )

    ensure_task_link_indexes()


def upgrade() -> None:
    ensure_budget_partidas_lineage_schema()
    ensure_task_link_structure()


def downgrade() -> None:
    # 0046 is intentionally non-destructive. It repairs production schema drift for objects that
    # should already exist since 0045, so downgrade must not drop lineage_id or task links.
    return None
