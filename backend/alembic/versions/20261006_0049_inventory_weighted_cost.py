"""Distinguish new weighted costs without changing legacy snapshots."""
from alembic import op
import sqlalchemy as sa


revision = "20261006_0049"
down_revision = "20260929_0048"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("movimientos_inventario", sa.Column("costing_policy", sa.String(32), nullable=True))
    op.add_column("materiales", sa.Column("costing_token", sa.String(36), nullable=True))


def downgrade():
    op.drop_column("materiales", "costing_token")
    op.drop_column("movimientos_inventario", "costing_policy")
