"""Add company branding fields for logo and document profile.

Revision ID: 20260610_0033
Revises: 20260609_0032
Create Date: 2026-06-10 13:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260610_0033"
down_revision: str | None = "20260609_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("empresas", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("nombre_comercial", sa.String(length=180), nullable=True))
        batch_op.add_column(sa.Column("logo_url", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("logo_blob_path", sa.String(length=1000), nullable=True))

    op.execute("UPDATE empresas SET nombre_comercial = name WHERE nombre_comercial IS NULL")


def downgrade() -> None:
    batch_kwargs = {"recreate": "always"} if using_sqlite() else {}
    with op.batch_alter_table("empresas", **batch_kwargs) as batch_op:
        batch_op.drop_column("logo_blob_path")
        batch_op.drop_column("logo_url")
        batch_op.drop_column("nombre_comercial")
