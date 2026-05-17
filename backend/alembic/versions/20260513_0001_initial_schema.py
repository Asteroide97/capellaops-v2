"""Initial schema for Capella Ops V2."""

from alembic import op
import sqlalchemy as sa


revision = "20260513_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "planes",
        sa.Column("code", sa.String(length=20), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("modules", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "usuarios",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_usuarios_email"), "usuarios", ["email"], unique=False)

    op.create_table(
        "empresas",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("plan_code", sa.String(length=20), nullable=False),
        sa.Column("access_status", sa.String(length=20), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["plan_code"], ["planes.code"]),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_empresas_access_status"), "empresas", ["access_status"], unique=False)
    op.create_index(op.f("ix_empresas_plan_code"), "empresas", ["plan_code"], unique=False)
    op.create_index(op.f("ix_empresas_slug"), "empresas", ["slug"], unique=False)

    op.create_table(
        "empresa_usuarios",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("usuario_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.UniqueConstraint("empresa_id", "usuario_id", name="uq_empresa_usuario"),
    )
    op.create_index(op.f("ix_empresa_usuarios_empresa_id"), "empresa_usuarios", ["empresa_id"], unique=False)
    op.create_index(op.f("ix_empresa_usuarios_usuario_id"), "empresa_usuarios", ["usuario_id"], unique=False)

    op.create_table(
        "empresa_modulos",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("module_name", sa.String(length=60), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.UniqueConstraint("empresa_id", "module_name", name="uq_empresa_modulo"),
    )
    op.create_index(op.f("ix_empresa_modulos_empresa_id"), "empresa_modulos", ["empresa_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=True),
        sa.Column("usuario_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_name", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
    )
    op.create_index(op.f("ix_audit_logs_empresa_id"), "audit_logs", ["empresa_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_usuario_id"), "audit_logs", ["usuario_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_usuario_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_empresa_id"), table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index(op.f("ix_empresa_modulos_empresa_id"), table_name="empresa_modulos")
    op.drop_table("empresa_modulos")

    op.drop_index(op.f("ix_empresa_usuarios_usuario_id"), table_name="empresa_usuarios")
    op.drop_index(op.f("ix_empresa_usuarios_empresa_id"), table_name="empresa_usuarios")
    op.drop_table("empresa_usuarios")

    op.drop_index(op.f("ix_empresas_slug"), table_name="empresas")
    op.drop_index(op.f("ix_empresas_plan_code"), table_name="empresas")
    op.drop_index(op.f("ix_empresas_access_status"), table_name="empresas")
    op.drop_table("empresas")

    op.drop_index(op.f("ix_usuarios_email"), table_name="usuarios")
    op.drop_table("usuarios")

    op.drop_table("planes")
