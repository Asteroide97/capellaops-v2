"""Add CRM core tables for clients, contacts, opportunities and activities.

Revision ID: 20260611_0036
Revises: 20260610_0035
Create Date: 2026-06-11 09:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260611_0036"
down_revision: str | None = "20260610_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crm_clientes",
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("nombre_comercial", sa.String(length=180), nullable=False),
        sa.Column("razon_social", sa.String(length=200), nullable=True),
        sa.Column("rfc", sa.String(length=40), nullable=True),
        sa.Column("tipo", sa.String(length=20), nullable=False, server_default=sa.text("'prospecto'")),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("telefono", sa.String(length=40), nullable=True),
        sa.Column("sitio_web", sa.String(length=255), nullable=True),
        sa.Column("direccion", sa.Text(), nullable=True),
        sa.Column("ciudad", sa.String(length=120), nullable=True),
        sa.Column("estado", sa.String(length=120), nullable=True),
        sa.Column("pais", sa.String(length=120), nullable=True),
        sa.Column("codigo_postal", sa.String(length=20), nullable=True),
        sa.Column("origen", sa.String(length=120), nullable=True),
        sa.Column("industria", sa.String(length=120), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("estatus", sa.String(length=20), nullable=False, server_default=sa.text("'activo'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint("tipo IN ('prospecto', 'cliente', 'otro')", name="ck_crm_cliente_tipo"),
        sa.CheckConstraint("estatus IN ('activo', 'inactivo')", name="ck_crm_cliente_estatus"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_clientes_empresa_id", "crm_clientes", ["empresa_id"])
    op.create_index("ix_crm_clientes_nombre_comercial", "crm_clientes", ["nombre_comercial"])
    op.create_index("ix_crm_clientes_rfc", "crm_clientes", ["rfc"])
    op.create_index("ix_crm_clientes_tipo", "crm_clientes", ["tipo"])
    op.create_index("ix_crm_clientes_origen", "crm_clientes", ["origen"])
    op.create_index("ix_crm_clientes_industria", "crm_clientes", ["industria"])
    op.create_index("ix_crm_clientes_estatus", "crm_clientes", ["estatus"])

    op.create_table(
        "crm_contactos",
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("cliente_id", sa.String(length=36), nullable=False),
        sa.Column("nombre", sa.String(length=160), nullable=False),
        sa.Column("puesto", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("telefono", sa.String(length=40), nullable=True),
        sa.Column("whatsapp", sa.String(length=40), nullable=True),
        sa.Column("principal", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["cliente_id"], ["crm_clientes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_contactos_empresa_id", "crm_contactos", ["empresa_id"])
    op.create_index("ix_crm_contactos_cliente_id", "crm_contactos", ["cliente_id"])
    op.create_index("ix_crm_contactos_nombre", "crm_contactos", ["nombre"])
    op.create_index("ix_crm_contactos_principal", "crm_contactos", ["principal"])
    op.create_index("ix_crm_contactos_activo", "crm_contactos", ["activo"])

    op.create_table(
        "crm_oportunidades",
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("cliente_id", sa.String(length=36), nullable=False),
        sa.Column("contacto_id", sa.String(length=36), nullable=True),
        sa.Column("titulo", sa.String(length=180), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("etapa", sa.String(length=20), nullable=False, server_default=sa.text("'nueva'")),
        sa.Column("monto_estimado", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("probabilidad", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fecha_estimada_cierre", sa.Date(), nullable=True),
        sa.Column("responsable_user_id", sa.String(length=36), nullable=True),
        sa.Column("origen", sa.String(length=120), nullable=True),
        sa.Column("motivo_perdida", sa.Text(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("cerrada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "etapa IN ('nueva', 'contactado', 'propuesta', 'negociacion', 'ganada', 'perdida')",
            name="ck_crm_oportunidad_etapa",
        ),
        sa.CheckConstraint("monto_estimado >= 0", name="ck_crm_oportunidad_monto_nonnegative"),
        sa.CheckConstraint("probabilidad >= 0 AND probabilidad <= 100", name="ck_crm_oportunidad_probabilidad_range"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["cliente_id"], ["crm_clientes.id"]),
        sa.ForeignKeyConstraint(["contacto_id"], ["crm_contactos.id"]),
        sa.ForeignKeyConstraint(["responsable_user_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_oportunidades_empresa_id", "crm_oportunidades", ["empresa_id"])
    op.create_index("ix_crm_oportunidades_cliente_id", "crm_oportunidades", ["cliente_id"])
    op.create_index("ix_crm_oportunidades_contacto_id", "crm_oportunidades", ["contacto_id"])
    op.create_index("ix_crm_oportunidades_titulo", "crm_oportunidades", ["titulo"])
    op.create_index("ix_crm_oportunidades_etapa", "crm_oportunidades", ["etapa"])
    op.create_index("ix_crm_oportunidades_responsable_user_id", "crm_oportunidades", ["responsable_user_id"])
    op.create_index("ix_crm_oportunidades_origen", "crm_oportunidades", ["origen"])
    op.create_index("ix_crm_oportunidades_activa", "crm_oportunidades", ["activa"])

    op.create_table(
        "crm_actividades",
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("cliente_id", sa.String(length=36), nullable=True),
        sa.Column("oportunidad_id", sa.String(length=36), nullable=True),
        sa.Column("contacto_id", sa.String(length=36), nullable=True),
        sa.Column("tipo", sa.String(length=20), nullable=False, server_default=sa.text("'nota'")),
        sa.Column("titulo", sa.String(length=180), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("fecha_actividad", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_vencimiento", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completada", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("completada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usuario_id", sa.String(length=36), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('llamada', 'email', 'reunion', 'tarea', 'nota', 'whatsapp', 'otro')",
            name="ck_crm_actividad_tipo",
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["cliente_id"], ["crm_clientes.id"]),
        sa.ForeignKeyConstraint(["oportunidad_id"], ["crm_oportunidades.id"]),
        sa.ForeignKeyConstraint(["contacto_id"], ["crm_contactos.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_actividades_empresa_id", "crm_actividades", ["empresa_id"])
    op.create_index("ix_crm_actividades_cliente_id", "crm_actividades", ["cliente_id"])
    op.create_index("ix_crm_actividades_oportunidad_id", "crm_actividades", ["oportunidad_id"])
    op.create_index("ix_crm_actividades_contacto_id", "crm_actividades", ["contacto_id"])
    op.create_index("ix_crm_actividades_tipo", "crm_actividades", ["tipo"])
    op.create_index("ix_crm_actividades_titulo", "crm_actividades", ["titulo"])
    op.create_index("ix_crm_actividades_fecha_actividad", "crm_actividades", ["fecha_actividad"])
    op.create_index("ix_crm_actividades_fecha_vencimiento", "crm_actividades", ["fecha_vencimiento"])
    op.create_index("ix_crm_actividades_completada", "crm_actividades", ["completada"])
    op.create_index("ix_crm_actividades_usuario_id", "crm_actividades", ["usuario_id"])
    op.create_index("ix_crm_actividades_activo", "crm_actividades", ["activo"])


def downgrade() -> None:
    op.drop_index("ix_crm_actividades_activo", table_name="crm_actividades")
    op.drop_index("ix_crm_actividades_usuario_id", table_name="crm_actividades")
    op.drop_index("ix_crm_actividades_completada", table_name="crm_actividades")
    op.drop_index("ix_crm_actividades_fecha_vencimiento", table_name="crm_actividades")
    op.drop_index("ix_crm_actividades_fecha_actividad", table_name="crm_actividades")
    op.drop_index("ix_crm_actividades_titulo", table_name="crm_actividades")
    op.drop_index("ix_crm_actividades_tipo", table_name="crm_actividades")
    op.drop_index("ix_crm_actividades_contacto_id", table_name="crm_actividades")
    op.drop_index("ix_crm_actividades_oportunidad_id", table_name="crm_actividades")
    op.drop_index("ix_crm_actividades_cliente_id", table_name="crm_actividades")
    op.drop_index("ix_crm_actividades_empresa_id", table_name="crm_actividades")
    op.drop_table("crm_actividades")

    op.drop_index("ix_crm_oportunidades_activa", table_name="crm_oportunidades")
    op.drop_index("ix_crm_oportunidades_origen", table_name="crm_oportunidades")
    op.drop_index("ix_crm_oportunidades_responsable_user_id", table_name="crm_oportunidades")
    op.drop_index("ix_crm_oportunidades_etapa", table_name="crm_oportunidades")
    op.drop_index("ix_crm_oportunidades_titulo", table_name="crm_oportunidades")
    op.drop_index("ix_crm_oportunidades_contacto_id", table_name="crm_oportunidades")
    op.drop_index("ix_crm_oportunidades_cliente_id", table_name="crm_oportunidades")
    op.drop_index("ix_crm_oportunidades_empresa_id", table_name="crm_oportunidades")
    op.drop_table("crm_oportunidades")

    op.drop_index("ix_crm_contactos_activo", table_name="crm_contactos")
    op.drop_index("ix_crm_contactos_principal", table_name="crm_contactos")
    op.drop_index("ix_crm_contactos_nombre", table_name="crm_contactos")
    op.drop_index("ix_crm_contactos_cliente_id", table_name="crm_contactos")
    op.drop_index("ix_crm_contactos_empresa_id", table_name="crm_contactos")
    op.drop_table("crm_contactos")

    op.drop_index("ix_crm_clientes_estatus", table_name="crm_clientes")
    op.drop_index("ix_crm_clientes_industria", table_name="crm_clientes")
    op.drop_index("ix_crm_clientes_origen", table_name="crm_clientes")
    op.drop_index("ix_crm_clientes_tipo", table_name="crm_clientes")
    op.drop_index("ix_crm_clientes_rfc", table_name="crm_clientes")
    op.drop_index("ix_crm_clientes_nombre_comercial", table_name="crm_clientes")
    op.drop_index("ix_crm_clientes_empresa_id", table_name="crm_clientes")
    op.drop_table("crm_clientes")
