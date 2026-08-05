"""Add budget lineage and budget-task links for PM.

Revision ID: 20260805_0045
Revises: 20260621_0044
Create Date: 2026-08-05 10:00:00.000000
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "20260805_0045"
down_revision: str | None = "20260621_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SYNC_STATUS_CHECK = "sync_status IN ('linked', 'detached', 'orphaned', 'conflict')"


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def backfill_lineage_ids() -> None:
    bind = op.get_bind()
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


def upgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}

    with op.batch_alter_table("pm_presupuesto_partidas", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("lineage_id", sa.String(length=36), nullable=True))

    backfill_lineage_ids()

    with op.batch_alter_table("pm_presupuesto_partidas", **batch_kwargs) as batch_op:
        batch_op.alter_column("lineage_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.create_unique_constraint(
            "uq_pm_presupuesto_partidas_presupuesto_lineage",
            ["presupuesto_id", "lineage_id"],
        )

    op.create_index(
        "ix_pm_presupuesto_partidas_lineage_id",
        "pm_presupuesto_partidas",
        ["lineage_id"],
        unique=False,
    )

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
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
        sa.ForeignKeyConstraint(["tarea_id"], ["pm_tareas.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_presupuesto_id"], ["pm_presupuestos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_partida_id"], ["pm_presupuesto_partidas.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_capitulo_id"], ["pm_presupuesto_partidas.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proyecto_id", "lineage_id", name="uq_pm_presupuesto_task_links_proyecto_lineage"),
    )
    op.create_index("ix_pm_presupuesto_task_links_empresa_id", "pm_presupuesto_task_links", ["empresa_id"], unique=False)
    op.create_index("ix_pm_presupuesto_task_links_proyecto_id", "pm_presupuesto_task_links", ["proyecto_id"], unique=False)
    op.create_index("ix_pm_presupuesto_task_links_lineage_id", "pm_presupuesto_task_links", ["lineage_id"], unique=False)
    op.create_index(
        "uq_pm_presupuesto_task_links_tarea_id_not_null",
        "pm_presupuesto_task_links",
        ["tarea_id"],
        unique=True,
        sqlite_where=sa.text("tarea_id IS NOT NULL"),
        mssql_where=sa.text("tarea_id IS NOT NULL"),
    )
    op.create_index(
        "ix_pm_presupuesto_task_links_source_presupuesto_id",
        "pm_presupuesto_task_links",
        ["source_presupuesto_id"],
        unique=False,
    )
    op.create_index(
        "ix_pm_presupuesto_task_links_source_partida_id",
        "pm_presupuesto_task_links",
        ["source_partida_id"],
        unique=False,
    )
    op.create_index(
        "ix_pm_presupuesto_task_links_sync_status",
        "pm_presupuesto_task_links",
        ["sync_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pm_presupuesto_task_links_sync_status", table_name="pm_presupuesto_task_links")
    op.drop_index("ix_pm_presupuesto_task_links_source_partida_id", table_name="pm_presupuesto_task_links")
    op.drop_index("ix_pm_presupuesto_task_links_source_presupuesto_id", table_name="pm_presupuesto_task_links")
    op.drop_index("uq_pm_presupuesto_task_links_tarea_id_not_null", table_name="pm_presupuesto_task_links")
    op.drop_index("ix_pm_presupuesto_task_links_lineage_id", table_name="pm_presupuesto_task_links")
    op.drop_index("ix_pm_presupuesto_task_links_proyecto_id", table_name="pm_presupuesto_task_links")
    op.drop_index("ix_pm_presupuesto_task_links_empresa_id", table_name="pm_presupuesto_task_links")
    op.drop_table("pm_presupuesto_task_links")

    op.drop_index("ix_pm_presupuesto_partidas_lineage_id", table_name="pm_presupuesto_partidas")

    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("pm_presupuesto_partidas", **batch_kwargs) as batch_op:
        batch_op.drop_constraint("uq_pm_presupuesto_partidas_presupuesto_lineage", type_="unique")
        batch_op.drop_column("lineage_id")
