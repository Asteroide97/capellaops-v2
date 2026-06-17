"""Add CRM quotes and quote items.

Revision ID: 20260617_0039
Revises: 20260616_0038
Create Date: 2026-06-17 10:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260617_0039"
down_revision: str | None = "20260616_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crm_cotizaciones",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("cliente_id", sa.String(length=36), nullable=False),
        sa.Column("contacto_id", sa.String(length=36), nullable=True),
        sa.Column("oportunidad_id", sa.String(length=36), nullable=True),
        sa.Column("folio", sa.String(length=40), nullable=False),
        sa.Column("titulo", sa.String(length=180), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("moneda", sa.String(length=10), nullable=False, server_default="MXN"),
        sa.Column("subtotal", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("descuento_total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("impuesto_total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("estatus", sa.String(length=20), nullable=False, server_default="borrador"),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=True),
        sa.Column("condiciones_pago", sa.Text(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("aceptada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rechazada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "estatus IN ('borrador', 'enviada', 'aceptada', 'rechazada', 'cancelada', 'vencida')",
            name="ck_crm_cotizacion_estatus",
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_crm_cotizacion_subtotal_nonnegative"),
        sa.CheckConstraint("descuento_total >= 0", name="ck_crm_cotizacion_descuento_nonnegative"),
        sa.CheckConstraint("impuesto_total >= 0", name="ck_crm_cotizacion_impuesto_nonnegative"),
        sa.CheckConstraint("total >= 0", name="ck_crm_cotizacion_total_nonnegative"),
        sa.ForeignKeyConstraint(["cliente_id"], ["crm_clientes.id"]),
        sa.ForeignKeyConstraint(["contacto_id"], ["crm_contactos.id"]),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["oportunidad_id"], ["crm_oportunidades.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("empresa_id", "folio", name="uq_crm_cotizacion_empresa_folio"),
    )
    op.create_index("ix_crm_cotizaciones_empresa_id", "crm_cotizaciones", ["empresa_id"], unique=False)
    op.create_index("ix_crm_cotizaciones_cliente_id", "crm_cotizaciones", ["cliente_id"], unique=False)
    op.create_index("ix_crm_cotizaciones_contacto_id", "crm_cotizaciones", ["contacto_id"], unique=False)
    op.create_index("ix_crm_cotizaciones_oportunidad_id", "crm_cotizaciones", ["oportunidad_id"], unique=False)
    op.create_index("ix_crm_cotizaciones_folio", "crm_cotizaciones", ["folio"], unique=False)
    op.create_index("ix_crm_cotizaciones_titulo", "crm_cotizaciones", ["titulo"], unique=False)
    op.create_index("ix_crm_cotizaciones_estatus", "crm_cotizaciones", ["estatus"], unique=False)
    op.create_index("ix_crm_cotizaciones_activo", "crm_cotizaciones", ["activo"], unique=False)

    op.create_table(
        "crm_cotizacion_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("cotizacion_id", sa.String(length=36), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("cantidad", sa.Numeric(18, 4), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(18, 4), nullable=False),
        sa.Column("descuento", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("impuesto_tasa", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("impuesto", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("cantidad > 0", name="ck_crm_cotizacion_item_cantidad_positive"),
        sa.CheckConstraint("precio_unitario >= 0", name="ck_crm_cotizacion_item_precio_nonnegative"),
        sa.CheckConstraint("descuento >= 0", name="ck_crm_cotizacion_item_descuento_nonnegative"),
        sa.CheckConstraint("impuesto_tasa >= 0", name="ck_crm_cotizacion_item_tasa_nonnegative"),
        sa.CheckConstraint("subtotal >= 0", name="ck_crm_cotizacion_item_subtotal_nonnegative"),
        sa.CheckConstraint("impuesto >= 0", name="ck_crm_cotizacion_item_impuesto_nonnegative"),
        sa.CheckConstraint("total >= 0", name="ck_crm_cotizacion_item_total_nonnegative"),
        sa.CheckConstraint("orden >= 0", name="ck_crm_cotizacion_item_orden_nonnegative"),
        sa.ForeignKeyConstraint(["cotizacion_id"], ["crm_cotizaciones.id"]),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_cotizacion_items_empresa_id", "crm_cotizacion_items", ["empresa_id"], unique=False)
    op.create_index("ix_crm_cotizacion_items_cotizacion_id", "crm_cotizacion_items", ["cotizacion_id"], unique=False)
    op.create_index("ix_crm_cotizacion_items_orden", "crm_cotizacion_items", ["orden"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_crm_cotizacion_items_orden", table_name="crm_cotizacion_items")
    op.drop_index("ix_crm_cotizacion_items_cotizacion_id", table_name="crm_cotizacion_items")
    op.drop_index("ix_crm_cotizacion_items_empresa_id", table_name="crm_cotizacion_items")
    op.drop_table("crm_cotizacion_items")

    op.drop_index("ix_crm_cotizaciones_activo", table_name="crm_cotizaciones")
    op.drop_index("ix_crm_cotizaciones_estatus", table_name="crm_cotizaciones")
    op.drop_index("ix_crm_cotizaciones_titulo", table_name="crm_cotizaciones")
    op.drop_index("ix_crm_cotizaciones_folio", table_name="crm_cotizaciones")
    op.drop_index("ix_crm_cotizaciones_oportunidad_id", table_name="crm_cotizaciones")
    op.drop_index("ix_crm_cotizaciones_contacto_id", table_name="crm_cotizaciones")
    op.drop_index("ix_crm_cotizaciones_cliente_id", table_name="crm_cotizaciones")
    op.drop_index("ix_crm_cotizaciones_empresa_id", table_name="crm_cotizaciones")
    op.drop_table("crm_cotizaciones")
