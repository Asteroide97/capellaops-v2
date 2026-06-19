"""Add POS approval settings and sale approvals.

Revision ID: 20260619_0043
Revises: 20260618_0042
Create Date: 2026-06-19 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260619_0043"
down_revision: str | None = "20260618_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pos_settings",
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column(
            "max_discount_percent_without_approval",
            sa.Numeric(precision=9, scale=4),
            server_default="15",
            nullable=False,
        ),
        sa.Column(
            "allow_negative_margin_without_approval",
            sa.Boolean(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "require_approval_below_cost",
            sa.Boolean(),
            server_default="1",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("empresa_id", name="uq_pos_settings_empresa"),
        sa.CheckConstraint(
            "max_discount_percent_without_approval >= 0 AND max_discount_percent_without_approval <= 100",
            name="ck_pos_settings_max_discount_percent_range",
        ),
    )
    op.create_index("ix_pos_settings_empresa_id", "pos_settings", ["empresa_id"], unique=False)

    op.create_table(
        "pos_sale_approvals",
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("sale_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by_usuario_id", sa.String(length=36), nullable=False),
        sa.Column("approved_by_usuario_id", sa.String(length=36), nullable=True),
        sa.Column("rejected_by_usuario_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("risk_summary_json", sa.JSON(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["sale_id"], ["ventas.id"]),
        sa.ForeignKeyConstraint(["requested_by_usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["approved_by_usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["rejected_by_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_pos_sale_approval_status",
        ),
    )
    op.create_index("ix_pos_sale_approvals_empresa_id", "pos_sale_approvals", ["empresa_id"], unique=False)
    op.create_index("ix_pos_sale_approvals_sale_id", "pos_sale_approvals", ["sale_id"], unique=False)
    op.create_index("ix_pos_sale_approvals_status", "pos_sale_approvals", ["status"], unique=False)
    op.create_index(
        "ix_pos_sale_approvals_requested_by_usuario_id",
        "pos_sale_approvals",
        ["requested_by_usuario_id"],
        unique=False,
    )
    op.create_index(
        "ix_pos_sale_approvals_approved_by_usuario_id",
        "pos_sale_approvals",
        ["approved_by_usuario_id"],
        unique=False,
    )
    op.create_index(
        "ix_pos_sale_approvals_rejected_by_usuario_id",
        "pos_sale_approvals",
        ["rejected_by_usuario_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pos_sale_approvals_rejected_by_usuario_id", table_name="pos_sale_approvals")
    op.drop_index("ix_pos_sale_approvals_approved_by_usuario_id", table_name="pos_sale_approvals")
    op.drop_index("ix_pos_sale_approvals_requested_by_usuario_id", table_name="pos_sale_approvals")
    op.drop_index("ix_pos_sale_approvals_status", table_name="pos_sale_approvals")
    op.drop_index("ix_pos_sale_approvals_sale_id", table_name="pos_sale_approvals")
    op.drop_index("ix_pos_sale_approvals_empresa_id", table_name="pos_sale_approvals")
    op.drop_table("pos_sale_approvals")

    op.drop_index("ix_pos_settings_empresa_id", table_name="pos_settings")
    op.drop_table("pos_settings")
