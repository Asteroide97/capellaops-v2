"""Rename plans to planes and add pending registrations."""

from alembic import op
import sqlalchemy as sa


revision = "20260515_0002"
down_revision = "20260513_0001"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _rename_plans_table(bind, inspector: sa.Inspector) -> None:
    has_planes = _table_exists(inspector, "planes")
    has_plans = _table_exists(inspector, "plans")

    if has_planes or not has_plans:
        return

    dialect_name = bind.dialect.name
    if dialect_name == "mssql":
        op.execute("EXEC sp_rename 'plans', 'planes'")
    else:
        op.rename_table("plans", "planes")


def _create_pending_registrations(inspector: sa.Inspector) -> None:
    if _table_exists(inspector, "pending_registrations"):
        return

    op.create_table(
        "pending_registrations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_nombre", sa.String(length=160), nullable=False),
        sa.Column("nombre_completo", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("plan_code", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["plan_code"], ["planes.code"]),
        sa.UniqueConstraint("email", name="uq_pending_registration_email"),
    )
    op.create_index(op.f("ix_pending_registrations_email"), "pending_registrations", ["email"], unique=False)
    op.create_index(op.f("ix_pending_registrations_plan_code"), "pending_registrations", ["plan_code"], unique=False)
    op.create_index(op.f("ix_pending_registrations_status"), "pending_registrations", ["status"], unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _rename_plans_table(bind, inspector)
    inspector = sa.inspect(bind)
    _create_pending_registrations(inspector)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "pending_registrations"):
        op.drop_index(op.f("ix_pending_registrations_status"), table_name="pending_registrations")
        op.drop_index(op.f("ix_pending_registrations_plan_code"), table_name="pending_registrations")
        op.drop_index(op.f("ix_pending_registrations_email"), table_name="pending_registrations")
        op.drop_table("pending_registrations")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "planes") and not _table_exists(inspector, "plans"):
        if bind.dialect.name == "mssql":
            op.execute("EXEC sp_rename 'planes', 'plans'")
        else:
            op.rename_table("planes", "plans")
