"""Add POS sale adjustments audit table.

Revision ID: 20260618_0042
Revises: 20260617_0041
Create Date: 2026-06-18 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_0042"
down_revision: str | None = "20260617_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pos_sale_adjustments",
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("sale_id", sa.String(length=36), nullable=False),
        sa.Column("line_id", sa.String(length=36), nullable=True),
        sa.Column("usuario_id", sa.String(length=36), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["sale_id"], ["ventas.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "tipo IN ('add_line', 'update_line', 'delete_line', 'recalculate')",
            name="ck_pos_sale_adjustment_tipo",
        ),
    )
    op.create_index("ix_pos_sale_adjustments_empresa_id", "pos_sale_adjustments", ["empresa_id"], unique=False)
    op.create_index("ix_pos_sale_adjustments_sale_id", "pos_sale_adjustments", ["sale_id"], unique=False)
    op.create_index("ix_pos_sale_adjustments_line_id", "pos_sale_adjustments", ["line_id"], unique=False)
    op.create_index("ix_pos_sale_adjustments_usuario_id", "pos_sale_adjustments", ["usuario_id"], unique=False)
    op.create_index("ix_pos_sale_adjustments_tipo", "pos_sale_adjustments", ["tipo"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pos_sale_adjustments_tipo", table_name="pos_sale_adjustments")
    op.drop_index("ix_pos_sale_adjustments_usuario_id", table_name="pos_sale_adjustments")
    op.drop_index("ix_pos_sale_adjustments_line_id", table_name="pos_sale_adjustments")
    op.drop_index("ix_pos_sale_adjustments_sale_id", table_name="pos_sale_adjustments")
    op.drop_index("ix_pos_sale_adjustments_empresa_id", table_name="pos_sale_adjustments")
    op.drop_table("pos_sale_adjustments")
