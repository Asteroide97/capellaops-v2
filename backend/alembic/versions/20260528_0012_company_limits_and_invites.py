"""Extend company, plan limits and company user invitations."""

from alembic import op
import sqlalchemy as sa


revision = "20260528_0012"
down_revision = "20260528_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("planes") as batch_op:
        batch_op.add_column(sa.Column("max_usuarios", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("max_almacenes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("max_facturas_mensuales", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("productos_ilimitados", sa.Boolean(), nullable=False, server_default="1"),
        )
        batch_op.add_column(
            sa.Column("ventas_ilimitadas", sa.Boolean(), nullable=False, server_default="1"),
        )
        batch_op.create_check_constraint(
            "ck_plan_max_usuarios_positive",
            "max_usuarios IS NULL OR max_usuarios > 0",
        )
        batch_op.create_check_constraint(
            "ck_plan_max_almacenes_positive",
            "max_almacenes IS NULL OR max_almacenes > 0",
        )
        batch_op.create_check_constraint(
            "ck_plan_max_facturas_positive",
            "max_facturas_mensuales IS NULL OR max_facturas_mensuales > 0",
        )

    op.add_column("empresas", sa.Column("razon_social", sa.String(length=180), nullable=True))
    op.add_column("empresas", sa.Column("rfc", sa.String(length=32), nullable=True))
    op.add_column("empresas", sa.Column("giro", sa.String(length=120), nullable=True))
    op.add_column("empresas", sa.Column("telefono", sa.String(length=40), nullable=True))
    op.add_column("empresas", sa.Column("email_contacto", sa.String(length=255), nullable=True))
    op.add_column("empresas", sa.Column("sitio_web", sa.String(length=255), nullable=True))
    op.add_column("empresas", sa.Column("pais", sa.String(length=80), nullable=True))
    op.add_column("empresas", sa.Column("estado", sa.String(length=80), nullable=True))
    op.add_column("empresas", sa.Column("ciudad", sa.String(length=80), nullable=True))
    op.add_column("empresas", sa.Column("codigo_postal", sa.String(length=20), nullable=True))
    op.add_column("empresas", sa.Column("direccion", sa.Text(), nullable=True))

    op.add_column(
        "empresa_usuarios",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_index("ix_empresa_usuarios_is_active", "empresa_usuarios", ["is_active"], unique=False)

    op.add_column("pending_registrations", sa.Column("empresa_razon_social", sa.String(length=180), nullable=True))
    op.add_column("pending_registrations", sa.Column("empresa_rfc", sa.String(length=32), nullable=True))
    op.add_column("pending_registrations", sa.Column("empresa_giro", sa.String(length=120), nullable=True))
    op.add_column("pending_registrations", sa.Column("empresa_telefono", sa.String(length=40), nullable=True))
    op.add_column("pending_registrations", sa.Column("empresa_email_contacto", sa.String(length=255), nullable=True))
    op.add_column("pending_registrations", sa.Column("empresa_pais", sa.String(length=80), nullable=True))
    op.add_column("pending_registrations", sa.Column("empresa_estado", sa.String(length=80), nullable=True))
    op.add_column("pending_registrations", sa.Column("empresa_ciudad", sa.String(length=80), nullable=True))
    op.add_column("pending_registrations", sa.Column("empresa_direccion", sa.String(length=500), nullable=True))

    op.create_table(
        "empresa_usuario_invitaciones",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=True),
        sa.Column("role", sa.String(length=40), nullable=False, server_default="user"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("invited_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("linked_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending', 'cancelled', 'accepted')",
            name="ck_empresa_usuario_invitacion_status",
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["linked_user_id"], ["usuarios.id"]),
    )
    op.create_index("ix_empresa_usuario_invitaciones_empresa_id", "empresa_usuario_invitaciones", ["empresa_id"], unique=False)
    op.create_index("ix_empresa_usuario_invitaciones_email", "empresa_usuario_invitaciones", ["email"], unique=False)
    op.create_index("ix_empresa_usuario_invitaciones_status", "empresa_usuario_invitaciones", ["status"], unique=False)
    op.create_index(
        "uq_empresa_usuario_invitacion_pending_email",
        "empresa_usuario_invitaciones",
        ["empresa_id", "email"],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
        mssql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_empresa_usuario_invitacion_pending_email", table_name="empresa_usuario_invitaciones")
    op.drop_index("ix_empresa_usuario_invitaciones_status", table_name="empresa_usuario_invitaciones")
    op.drop_index("ix_empresa_usuario_invitaciones_email", table_name="empresa_usuario_invitaciones")
    op.drop_index("ix_empresa_usuario_invitaciones_empresa_id", table_name="empresa_usuario_invitaciones")
    op.drop_table("empresa_usuario_invitaciones")

    op.drop_column("pending_registrations", "empresa_direccion")
    op.drop_column("pending_registrations", "empresa_ciudad")
    op.drop_column("pending_registrations", "empresa_estado")
    op.drop_column("pending_registrations", "empresa_pais")
    op.drop_column("pending_registrations", "empresa_email_contacto")
    op.drop_column("pending_registrations", "empresa_telefono")
    op.drop_column("pending_registrations", "empresa_giro")
    op.drop_column("pending_registrations", "empresa_rfc")
    op.drop_column("pending_registrations", "empresa_razon_social")

    op.drop_index("ix_empresa_usuarios_is_active", table_name="empresa_usuarios")
    op.drop_column("empresa_usuarios", "is_active")

    op.drop_column("empresas", "direccion")
    op.drop_column("empresas", "codigo_postal")
    op.drop_column("empresas", "ciudad")
    op.drop_column("empresas", "estado")
    op.drop_column("empresas", "pais")
    op.drop_column("empresas", "sitio_web")
    op.drop_column("empresas", "email_contacto")
    op.drop_column("empresas", "telefono")
    op.drop_column("empresas", "giro")
    op.drop_column("empresas", "rfc")
    op.drop_column("empresas", "razon_social")

    with op.batch_alter_table("planes") as batch_op:
        batch_op.drop_constraint("ck_plan_max_facturas_positive", type_="check")
        batch_op.drop_constraint("ck_plan_max_almacenes_positive", type_="check")
        batch_op.drop_constraint("ck_plan_max_usuarios_positive", type_="check")
        batch_op.drop_column("ventas_ilimitadas")
        batch_op.drop_column("productos_ilimitados")
        batch_op.drop_column("max_facturas_mensuales")
        batch_op.drop_column("max_almacenes")
        batch_op.drop_column("max_usuarios")
