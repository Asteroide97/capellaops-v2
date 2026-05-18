"""Add last_login_at to usuarios."""

from alembic import op
import sqlalchemy as sa


revision = "20260517_0005"
down_revision = "20260517_0004"
branch_labels = None
depends_on = None


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _column_exists(inspector, "usuarios", "last_login_at"):
        op.add_column("usuarios", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _column_exists(inspector, "usuarios", "last_login_at"):
        op.drop_column("usuarios", "last_login_at")
