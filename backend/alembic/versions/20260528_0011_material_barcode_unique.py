"""Add filtered unique index for material barcode per company."""

from alembic import op
import sqlalchemy as sa


revision = "20260528_0011"
down_revision = "20260527_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_material_empresa_codigo_barras",
        "materiales",
        ["empresa_id", "codigo_barras"],
        unique=True,
        sqlite_where=sa.text("codigo_barras IS NOT NULL"),
        mssql_where=sa.text("codigo_barras IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_material_empresa_codigo_barras", table_name="materiales")
