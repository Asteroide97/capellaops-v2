"""Add POS cash shifts and link sales to shifts.

Revision ID: 20260609_0027
Revises: 20260608_0026
Create Date: 2026-06-09 10:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260609_0027"
down_revision: str | None = "20260608_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    op.create_table(
        "pos_turnos_caja",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("almacen_id", sa.String(length=36), nullable=False),
        sa.Column("folio", sa.String(length=60), nullable=False),
        sa.Column("usuario_apertura_id", sa.String(length=36), nullable=False),
        sa.Column("usuario_cierre_id", sa.String(length=36), nullable=True),
        sa.Column("estatus", sa.String(length=20), nullable=False, server_default=sa.text("'abierta'")),
        sa.Column("fondo_inicial", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_ventas", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_efectivo", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_tarjeta", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_transferencia", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_otro", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("ingresos_manuales", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("retiros_manuales", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("efectivo_contado", sa.Numeric(18, 4), nullable=True),
        sa.Column("diferencia", sa.Numeric(18, 4), nullable=True),
        sa.Column("notas_apertura", sa.Text(), nullable=True),
        sa.Column("notas_cierre", sa.Text(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("estatus IN ('abierta', 'cerrada', 'cancelada')", name="ck_pos_turno_estatus"),
        sa.CheckConstraint("fondo_inicial >= 0", name="ck_pos_turno_fondo_inicial_nonnegative"),
        sa.CheckConstraint("total_ventas >= 0", name="ck_pos_turno_total_ventas_nonnegative"),
        sa.CheckConstraint("total_efectivo >= 0", name="ck_pos_turno_total_efectivo_nonnegative"),
        sa.CheckConstraint("total_tarjeta >= 0", name="ck_pos_turno_total_tarjeta_nonnegative"),
        sa.CheckConstraint("total_transferencia >= 0", name="ck_pos_turno_total_transferencia_nonnegative"),
        sa.CheckConstraint("total_otro >= 0", name="ck_pos_turno_total_otro_nonnegative"),
        sa.CheckConstraint("ingresos_manuales >= 0", name="ck_pos_turno_ingresos_nonnegative"),
        sa.CheckConstraint("retiros_manuales >= 0", name="ck_pos_turno_retiros_nonnegative"),
        sa.CheckConstraint(
            "efectivo_contado IS NULL OR efectivo_contado >= 0",
            name="ck_pos_turno_efectivo_contado_nonnegative",
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["almacen_id"], ["almacenes.id"]),
        sa.ForeignKeyConstraint(["usuario_apertura_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["usuario_cierre_id"], ["usuarios.id"]),
        sa.UniqueConstraint("empresa_id", "folio", name="uq_pos_turno_empresa_folio"),
    )
    op.create_index("ix_pos_turnos_caja_empresa_id", "pos_turnos_caja", ["empresa_id"], unique=False)
    op.create_index("ix_pos_turnos_caja_almacen_id", "pos_turnos_caja", ["almacen_id"], unique=False)
    op.create_index("ix_pos_turnos_caja_folio", "pos_turnos_caja", ["folio"], unique=False)
    op.create_index("ix_pos_turnos_caja_estatus", "pos_turnos_caja", ["estatus"], unique=False)
    op.create_index("ix_pos_turnos_caja_usuario_apertura_id", "pos_turnos_caja", ["usuario_apertura_id"], unique=False)
    op.create_index("ix_pos_turnos_caja_usuario_cierre_id", "pos_turnos_caja", ["usuario_cierre_id"], unique=False)

    op.create_table(
        "pos_turnos_caja_movimientos",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("turno_id", sa.String(length=36), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("monto", sa.Numeric(18, 4), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("usuario_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tipo IN ('ingreso', 'retiro')", name="ck_pos_turno_mov_tipo"),
        sa.CheckConstraint("monto > 0", name="ck_pos_turno_mov_monto_positive"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["turno_id"], ["pos_turnos_caja.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
    )
    op.create_index(
        "ix_pos_turnos_caja_movimientos_empresa_id",
        "pos_turnos_caja_movimientos",
        ["empresa_id"],
        unique=False,
    )
    op.create_index(
        "ix_pos_turnos_caja_movimientos_turno_id",
        "pos_turnos_caja_movimientos",
        ["turno_id"],
        unique=False,
    )
    op.create_index(
        "ix_pos_turnos_caja_movimientos_tipo",
        "pos_turnos_caja_movimientos",
        ["tipo"],
        unique=False,
    )
    op.create_index(
        "ix_pos_turnos_caja_movimientos_usuario_id",
        "pos_turnos_caja_movimientos",
        ["usuario_id"],
        unique=False,
    )

    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("ventas", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("turno_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_ventas_turno_id", ["turno_id"], unique=False)
        batch_op.create_foreign_key("fk_ventas_turno_id", "pos_turnos_caja", ["turno_id"], ["id"])


def downgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("ventas", **batch_kwargs) as batch_op:
        batch_op.drop_constraint("fk_ventas_turno_id", type_="foreignkey")
        batch_op.drop_index("ix_ventas_turno_id")
        batch_op.drop_column("turno_id")

    op.drop_index("ix_pos_turnos_caja_movimientos_usuario_id", table_name="pos_turnos_caja_movimientos")
    op.drop_index("ix_pos_turnos_caja_movimientos_tipo", table_name="pos_turnos_caja_movimientos")
    op.drop_index("ix_pos_turnos_caja_movimientos_turno_id", table_name="pos_turnos_caja_movimientos")
    op.drop_index("ix_pos_turnos_caja_movimientos_empresa_id", table_name="pos_turnos_caja_movimientos")
    op.drop_table("pos_turnos_caja_movimientos")

    op.drop_index("ix_pos_turnos_caja_usuario_cierre_id", table_name="pos_turnos_caja")
    op.drop_index("ix_pos_turnos_caja_usuario_apertura_id", table_name="pos_turnos_caja")
    op.drop_index("ix_pos_turnos_caja_estatus", table_name="pos_turnos_caja")
    op.drop_index("ix_pos_turnos_caja_folio", table_name="pos_turnos_caja")
    op.drop_index("ix_pos_turnos_caja_almacen_id", table_name="pos_turnos_caja")
    op.drop_index("ix_pos_turnos_caja_empresa_id", table_name="pos_turnos_caja")
    op.drop_table("pos_turnos_caja")
