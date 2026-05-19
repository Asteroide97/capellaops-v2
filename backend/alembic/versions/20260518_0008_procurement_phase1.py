"""Add procurement phase 1 tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260518_0008"
down_revision = "20260518_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proveedores",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("nombre", sa.String(length=160), nullable=False),
        sa.Column("contacto_nombre", sa.String(length=160), nullable=True),
        sa.Column("correo", sa.String(length=255), nullable=True),
        sa.Column("telefono", sa.String(length=40), nullable=True),
        sa.Column("direccion", sa.Text(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
    )
    op.create_index("ix_proveedores_empresa_id", "proveedores", ["empresa_id"], unique=False)
    op.create_index("ix_proveedores_activo", "proveedores", ["activo"], unique=False)

    op.create_table(
        "requisiciones",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("folio", sa.String(length=60), nullable=False),
        sa.Column("solicitante_user_id", sa.String(length=36), nullable=False),
        sa.Column("estatus", sa.String(length=20), nullable=False, server_default=sa.text("'borrador'")),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "estatus IN ('borrador', 'enviada', 'aprobada', 'rechazada', 'surtida', 'cancelada')",
            name="ck_requisicion_estatus",
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["solicitante_user_id"], ["usuarios.id"]),
        sa.UniqueConstraint("empresa_id", "folio", name="uq_requisicion_empresa_folio"),
    )
    op.create_index("ix_requisiciones_empresa_id", "requisiciones", ["empresa_id"], unique=False)
    op.create_index("ix_requisiciones_folio", "requisiciones", ["folio"], unique=False)
    op.create_index("ix_requisiciones_solicitante_user_id", "requisiciones", ["solicitante_user_id"], unique=False)
    op.create_index("ix_requisiciones_estatus", "requisiciones", ["estatus"], unique=False)

    op.create_table(
        "requisiciones_detalles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("requisicion_id", sa.String(length=36), nullable=False),
        sa.Column("material_id", sa.String(length=36), nullable=False),
        sa.Column("cantidad", sa.Numeric(18, 4), nullable=False),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.CheckConstraint("cantidad > 0", name="ck_requisicion_detalle_cantidad_positive"),
        sa.ForeignKeyConstraint(["requisicion_id"], ["requisiciones.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materiales.id"]),
    )
    op.create_index("ix_requisiciones_detalles_requisicion_id", "requisiciones_detalles", ["requisicion_id"], unique=False)
    op.create_index("ix_requisiciones_detalles_material_id", "requisiciones_detalles", ["material_id"], unique=False)

    op.create_table(
        "ordenes_compra",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("folio", sa.String(length=60), nullable=False),
        sa.Column("proveedor_id", sa.String(length=36), nullable=False),
        sa.Column("almacen_destino_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("estatus", sa.String(length=20), nullable=False, server_default=sa.text("'borrador'")),
        sa.Column("subtotal", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("descuento_total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("impuesto_total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "estatus IN ('borrador', 'emitida', 'recibida_parcial', 'recibida', 'cancelada')",
            name="ck_orden_compra_estatus",
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_orden_compra_subtotal_nonnegative"),
        sa.CheckConstraint("descuento_total >= 0", name="ck_orden_compra_descuento_nonnegative"),
        sa.CheckConstraint("impuesto_total >= 0", name="ck_orden_compra_impuesto_nonnegative"),
        sa.CheckConstraint("total >= 0", name="ck_orden_compra_total_nonnegative"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"]),
        sa.ForeignKeyConstraint(["almacen_destino_id"], ["almacenes.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["usuarios.id"]),
        sa.UniqueConstraint("empresa_id", "folio", name="uq_orden_compra_empresa_folio"),
    )
    op.create_index("ix_ordenes_compra_empresa_id", "ordenes_compra", ["empresa_id"], unique=False)
    op.create_index("ix_ordenes_compra_folio", "ordenes_compra", ["folio"], unique=False)
    op.create_index("ix_ordenes_compra_proveedor_id", "ordenes_compra", ["proveedor_id"], unique=False)
    op.create_index("ix_ordenes_compra_almacen_destino_id", "ordenes_compra", ["almacen_destino_id"], unique=False)
    op.create_index("ix_ordenes_compra_created_by_user_id", "ordenes_compra", ["created_by_user_id"], unique=False)
    op.create_index("ix_ordenes_compra_estatus", "ordenes_compra", ["estatus"], unique=False)

    op.create_table(
        "ordenes_compra_detalles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("orden_compra_id", sa.String(length=36), nullable=False),
        sa.Column("material_id", sa.String(length=36), nullable=False),
        sa.Column("cantidad", sa.Numeric(18, 4), nullable=False),
        sa.Column("cantidad_recibida", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("costo_unitario", sa.Numeric(18, 4), nullable=False),
        sa.Column("subtotal_linea", sa.Numeric(18, 4), nullable=False),
        sa.Column("total_linea", sa.Numeric(18, 4), nullable=False),
        sa.CheckConstraint("cantidad > 0", name="ck_orden_compra_detalle_cantidad_positive"),
        sa.CheckConstraint("cantidad_recibida >= 0", name="ck_orden_compra_detalle_recibida_nonnegative"),
        sa.CheckConstraint("costo_unitario >= 0", name="ck_orden_compra_detalle_costo_nonnegative"),
        sa.CheckConstraint("subtotal_linea >= 0", name="ck_orden_compra_detalle_subtotal_nonnegative"),
        sa.CheckConstraint("total_linea >= 0", name="ck_orden_compra_detalle_total_nonnegative"),
        sa.ForeignKeyConstraint(["orden_compra_id"], ["ordenes_compra.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materiales.id"]),
    )
    op.create_index("ix_ordenes_compra_detalles_orden_compra_id", "ordenes_compra_detalles", ["orden_compra_id"], unique=False)
    op.create_index("ix_ordenes_compra_detalles_material_id", "ordenes_compra_detalles", ["material_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ordenes_compra_detalles_material_id", table_name="ordenes_compra_detalles")
    op.drop_index("ix_ordenes_compra_detalles_orden_compra_id", table_name="ordenes_compra_detalles")
    op.drop_table("ordenes_compra_detalles")

    op.drop_index("ix_ordenes_compra_estatus", table_name="ordenes_compra")
    op.drop_index("ix_ordenes_compra_created_by_user_id", table_name="ordenes_compra")
    op.drop_index("ix_ordenes_compra_almacen_destino_id", table_name="ordenes_compra")
    op.drop_index("ix_ordenes_compra_proveedor_id", table_name="ordenes_compra")
    op.drop_index("ix_ordenes_compra_folio", table_name="ordenes_compra")
    op.drop_index("ix_ordenes_compra_empresa_id", table_name="ordenes_compra")
    op.drop_table("ordenes_compra")

    op.drop_index("ix_requisiciones_detalles_material_id", table_name="requisiciones_detalles")
    op.drop_index("ix_requisiciones_detalles_requisicion_id", table_name="requisiciones_detalles")
    op.drop_table("requisiciones_detalles")

    op.drop_index("ix_requisiciones_estatus", table_name="requisiciones")
    op.drop_index("ix_requisiciones_solicitante_user_id", table_name="requisiciones")
    op.drop_index("ix_requisiciones_folio", table_name="requisiciones")
    op.drop_index("ix_requisiciones_empresa_id", table_name="requisiciones")
    op.drop_table("requisiciones")

    op.drop_index("ix_proveedores_activo", table_name="proveedores")
    op.drop_index("ix_proveedores_empresa_id", table_name="proveedores")
    op.drop_table("proveedores")
