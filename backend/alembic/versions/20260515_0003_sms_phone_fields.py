"""Add SMS phone fields for pending registrations and users."""

from alembic import op
import sqlalchemy as sa


revision = "20260515_0003"
down_revision = "20260515_0002"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "usuarios"):
        if not _column_exists(inspector, "usuarios", "country_code"):
            op.add_column("usuarios", sa.Column("country_code", sa.String(length=8), nullable=True))
        if not _column_exists(inspector, "usuarios", "phone_number"):
            op.add_column("usuarios", sa.Column("phone_number", sa.String(length=32), nullable=True))
        if not _column_exists(inspector, "usuarios", "phone_e164"):
            op.add_column("usuarios", sa.Column("phone_e164", sa.String(length=20), nullable=True))
        if not _column_exists(inspector, "usuarios", "phone_verified_at"):
            op.add_column("usuarios", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True))

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "usuarios") and not _index_exists(inspector, "usuarios", "uq_usuarios_phone_e164"):
        op.create_index(
            "uq_usuarios_phone_e164",
            "usuarios",
            ["phone_e164"],
            unique=True,
            sqlite_where=sa.text("phone_e164 IS NOT NULL"),
            mssql_where=sa.text("phone_e164 IS NOT NULL"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "pending_registrations"):
        if not _column_exists(inspector, "pending_registrations", "country_code"):
            op.add_column("pending_registrations", sa.Column("country_code", sa.String(length=8), nullable=True))
        if not _column_exists(inspector, "pending_registrations", "phone_number"):
            op.add_column("pending_registrations", sa.Column("phone_number", sa.String(length=32), nullable=True))
        if not _column_exists(inspector, "pending_registrations", "phone_e164"):
            op.add_column("pending_registrations", sa.Column("phone_e164", sa.String(length=20), nullable=True))

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "pending_registrations") and not _index_exists(
        inspector,
        "pending_registrations",
        "uq_pending_registrations_phone_e164",
    ):
        op.create_index(
            "uq_pending_registrations_phone_e164",
            "pending_registrations",
            ["phone_e164"],
            unique=True,
            sqlite_where=sa.text("phone_e164 IS NOT NULL AND status = 'pending'"),
            mssql_where=sa.text("phone_e164 IS NOT NULL AND status = 'pending'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "pending_registrations") and _index_exists(
        inspector,
        "pending_registrations",
        "uq_pending_registrations_phone_e164",
    ):
        op.drop_index("uq_pending_registrations_phone_e164", table_name="pending_registrations")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "pending_registrations"):
        if _column_exists(inspector, "pending_registrations", "phone_e164"):
            op.drop_column("pending_registrations", "phone_e164")
        if _column_exists(inspector, "pending_registrations", "phone_number"):
            op.drop_column("pending_registrations", "phone_number")
        if _column_exists(inspector, "pending_registrations", "country_code"):
            op.drop_column("pending_registrations", "country_code")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "usuarios") and _index_exists(inspector, "usuarios", "uq_usuarios_phone_e164"):
        op.drop_index("uq_usuarios_phone_e164", table_name="usuarios")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "usuarios"):
        if _column_exists(inspector, "usuarios", "phone_verified_at"):
            op.drop_column("usuarios", "phone_verified_at")
        if _column_exists(inspector, "usuarios", "phone_e164"):
            op.drop_column("usuarios", "phone_e164")
        if _column_exists(inspector, "usuarios", "phone_number"):
            op.drop_column("usuarios", "phone_number")
        if _column_exists(inspector, "usuarios", "country_code"):
            op.drop_column("usuarios", "country_code")
