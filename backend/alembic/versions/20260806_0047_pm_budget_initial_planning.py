"""Add PM budget initial planning fields and prerequisites.

Revision ID: 20260806_0047
Revises: 20260805_0046
Create Date: 2026-08-06 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260806_0047"
down_revision: str | None = "20260805_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEPENDENCY_TYPE_CHECK = (
    "tipo_dependencia IN ('finish_to_start', 'start_to_start', 'finish_to_finish', 'start_to_finish')"
)


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def batch_kwargs() -> dict[str, str]:
    return {"recreate": "always"} if using_sqlite() else {}


def upgrade() -> None:
    with op.batch_alter_table("pm_presupuesto_partidas", **batch_kwargs()) as batch_op:
        batch_op.add_column(sa.Column("fecha_inicio_sugerida", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("fecha_fin_sugerida", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("duracion_dias_sugerida", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("responsable_sugerido_usuario_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("notas_planificacion", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_pm_presupuesto_partidas_responsable_sugerido_usuario_id",
            "usuarios",
            ["responsable_sugerido_usuario_id"],
            ["id"],
        )

    op.create_index(
        "ix_pm_presupuesto_partidas_responsable_sugerido_usuario_id",
        "pm_presupuesto_partidas",
        ["responsable_sugerido_usuario_id"],
        unique=False,
    )

    op.create_table(
        "pm_presupuesto_partida_prerequisitos",
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("proyecto_id", sa.String(length=36), nullable=False),
        sa.Column("presupuesto_id", sa.String(length=36), nullable=False),
        sa.Column("partida_id", sa.String(length=36), nullable=False),
        sa.Column("prerequisito_partida_id", sa.String(length=36), nullable=False),
        sa.Column("partida_lineage_id", sa.String(length=36), nullable=False),
        sa.Column("prerequisito_lineage_id", sa.String(length=36), nullable=False),
        sa.Column(
            "tipo_dependencia",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'finish_to_start'"),
        ),
        sa.Column("desfase_dias", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(DEPENDENCY_TYPE_CHECK, name="ck_pm_presupuesto_partida_prerequisitos_tipo"),
        sa.CheckConstraint("desfase_dias >= 0", name="ck_pm_presupuesto_partida_prerequisitos_desfase"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], name="fk_pm_presupuesto_partida_prerequisitos_empresa_id"),
        sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"], name="fk_pm_presupuesto_partida_prerequisitos_proyecto_id"),
        sa.ForeignKeyConstraint(["presupuesto_id"], ["pm_presupuestos.id"], name="fk_pm_presupuesto_partida_prerequisitos_presupuesto_id"),
        sa.ForeignKeyConstraint(["partida_id"], ["pm_presupuesto_partidas.id"], name="fk_pm_presupuesto_partida_prerequisitos_partida_id"),
        sa.ForeignKeyConstraint(
            ["prerequisito_partida_id"],
            ["pm_presupuesto_partidas.id"],
            name="fk_pm_presupuesto_partida_prerequisitos_prerequisito_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pm_presupuesto_partida_prerequisitos"),
        sa.UniqueConstraint(
            "presupuesto_id",
            "partida_lineage_id",
            "prerequisito_lineage_id",
            "tipo_dependencia",
            name="uq_pm_presupuesto_partida_prerequisitos_lineage",
        ),
    )
    op.create_index(
        "ix_pm_presupuesto_partida_prerequisitos_empresa_id",
        "pm_presupuesto_partida_prerequisitos",
        ["empresa_id"],
        unique=False,
    )
    op.create_index(
        "ix_pm_presupuesto_partida_prerequisitos_proyecto_id",
        "pm_presupuesto_partida_prerequisitos",
        ["proyecto_id"],
        unique=False,
    )
    op.create_index(
        "ix_pm_presupuesto_partida_prerequisitos_presupuesto_id",
        "pm_presupuesto_partida_prerequisitos",
        ["presupuesto_id"],
        unique=False,
    )
    op.create_index(
        "ix_pm_presupuesto_partida_prerequisitos_partida_id",
        "pm_presupuesto_partida_prerequisitos",
        ["partida_id"],
        unique=False,
    )
    op.create_index(
        "ix_pm_presupuesto_partida_prerequisitos_prerequisito_id",
        "pm_presupuesto_partida_prerequisitos",
        ["prerequisito_partida_id"],
        unique=False,
    )
    op.create_index(
        "ix_pm_presupuesto_partida_prerequisitos_partida_lineage",
        "pm_presupuesto_partida_prerequisitos",
        ["partida_lineage_id"],
        unique=False,
    )
    op.create_index(
        "ix_pm_presupuesto_partida_prerequisitos_prerequisito_lineage",
        "pm_presupuesto_partida_prerequisitos",
        ["prerequisito_lineage_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pm_presupuesto_partida_prerequisitos_prerequisito_lineage",
        table_name="pm_presupuesto_partida_prerequisitos",
    )
    op.drop_index(
        "ix_pm_presupuesto_partida_prerequisitos_partida_lineage",
        table_name="pm_presupuesto_partida_prerequisitos",
    )
    op.drop_index(
        "ix_pm_presupuesto_partida_prerequisitos_prerequisito_id",
        table_name="pm_presupuesto_partida_prerequisitos",
    )
    op.drop_index(
        "ix_pm_presupuesto_partida_prerequisitos_partida_id",
        table_name="pm_presupuesto_partida_prerequisitos",
    )
    op.drop_index(
        "ix_pm_presupuesto_partida_prerequisitos_presupuesto_id",
        table_name="pm_presupuesto_partida_prerequisitos",
    )
    op.drop_index(
        "ix_pm_presupuesto_partida_prerequisitos_proyecto_id",
        table_name="pm_presupuesto_partida_prerequisitos",
    )
    op.drop_index(
        "ix_pm_presupuesto_partida_prerequisitos_empresa_id",
        table_name="pm_presupuesto_partida_prerequisitos",
    )
    op.drop_table("pm_presupuesto_partida_prerequisitos")

    op.drop_index(
        "ix_pm_presupuesto_partidas_responsable_sugerido_usuario_id",
        table_name="pm_presupuesto_partidas",
    )
    with op.batch_alter_table("pm_presupuesto_partidas", **batch_kwargs()) as batch_op:
        batch_op.drop_constraint("fk_pm_presupuesto_partidas_responsable_sugerido_usuario_id", type_="foreignkey")
        batch_op.drop_column("notas_planificacion")
        batch_op.drop_column("responsable_sugerido_usuario_id")
        batch_op.drop_column("duracion_dias_sugerida")
        batch_op.drop_column("fecha_fin_sugerida")
        batch_op.drop_column("fecha_inicio_sugerida")
