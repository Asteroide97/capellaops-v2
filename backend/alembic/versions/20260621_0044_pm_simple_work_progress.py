"""Add simple PM work progress tracking.

Revision ID: 20260621_0044
Revises: 20260619_0043
Create Date: 2026-06-21 10:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260621_0044"
down_revision: str | None = "20260619_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OPERATIONAL_STATUS_CHECK = (
    "estado_operativo IN ('nuevo', 'cotizado', 'autorizado', 'en_proceso', 'pausado', "
    "'pendiente_cliente', 'listo_entrega', 'entregado', 'cobrado', 'cancelado')"
)


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}

    with op.batch_alter_table("pm_proyectos", **batch_kwargs) as batch_op:
        batch_op.add_column(
            sa.Column("estado_operativo", sa.String(length=30), nullable=False, server_default=sa.text("'nuevo'"))
        )
        batch_op.add_column(sa.Column("proximo_paso", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("bloqueo_actual", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ultima_actualizacion_avance_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_check_constraint("ck_pm_proyectos_estado_operativo", OPERATIONAL_STATUS_CHECK)

    op.create_index("ix_pm_proyectos_estado_operativo", "pm_proyectos", ["estado_operativo"], unique=False)
    op.create_index(
        "ix_pm_proyectos_ultima_actualizacion_avance_at",
        "pm_proyectos",
        ["ultima_actualizacion_avance_at"],
        unique=False,
    )

    op.execute("UPDATE pm_proyectos SET estado_operativo = 'nuevo' WHERE estado_operativo IS NULL")

    op.create_table(
        "pm_trabajo_avances",
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("proyecto_id", sa.String(length=36), nullable=False),
        sa.Column("usuario_id", sa.String(length=36), nullable=True),
        sa.Column("comentario", sa.Text(), nullable=False),
        sa.Column("avance_porcentaje", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0"),
        sa.Column("estado_operativo", sa.String(length=30), nullable=False, server_default=sa.text("'nuevo'")),
        sa.Column("proximo_paso", sa.String(length=255), nullable=True),
        sa.Column("bloqueo_actual", sa.Text(), nullable=True),
        sa.Column("fecha_compromiso", sa.Date(), nullable=True),
        sa.Column("evidencia_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "avance_porcentaje >= 0 AND avance_porcentaje <= 100",
            name="ck_pm_trabajo_avances_porcentaje",
        ),
        sa.CheckConstraint(OPERATIONAL_STATUS_CHECK, name="ck_pm_trabajo_avances_estado_operativo"),
    )
    op.create_index("ix_pm_trabajo_avances_empresa_id", "pm_trabajo_avances", ["empresa_id"], unique=False)
    op.create_index("ix_pm_trabajo_avances_proyecto_id", "pm_trabajo_avances", ["proyecto_id"], unique=False)
    op.create_index("ix_pm_trabajo_avances_usuario_id", "pm_trabajo_avances", ["usuario_id"], unique=False)
    op.create_index(
        "ix_pm_trabajo_avances_estado_operativo",
        "pm_trabajo_avances",
        ["estado_operativo"],
        unique=False,
    )
    op.create_index("ix_pm_trabajo_avances_created_at", "pm_trabajo_avances", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pm_trabajo_avances_created_at", table_name="pm_trabajo_avances")
    op.drop_index("ix_pm_trabajo_avances_estado_operativo", table_name="pm_trabajo_avances")
    op.drop_index("ix_pm_trabajo_avances_usuario_id", table_name="pm_trabajo_avances")
    op.drop_index("ix_pm_trabajo_avances_proyecto_id", table_name="pm_trabajo_avances")
    op.drop_index("ix_pm_trabajo_avances_empresa_id", table_name="pm_trabajo_avances")
    op.drop_table("pm_trabajo_avances")

    op.drop_index("ix_pm_proyectos_ultima_actualizacion_avance_at", table_name="pm_proyectos")
    op.drop_index("ix_pm_proyectos_estado_operativo", table_name="pm_proyectos")

    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("pm_proyectos", **batch_kwargs) as batch_op:
        batch_op.drop_constraint("ck_pm_proyectos_estado_operativo", type_="check")
        batch_op.drop_column("ultima_actualizacion_avance_at")
        batch_op.drop_column("bloqueo_actual")
        batch_op.drop_column("proximo_paso")
        batch_op.drop_column("estado_operativo")
