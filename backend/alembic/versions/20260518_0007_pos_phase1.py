"""Add POS phase 1 sales tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260518_0007"
down_revision = "20260518_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ventas",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("folio", sa.String(length=60), nullable=False),
        sa.Column("almacen_id", sa.String(length=36), nullable=False),
        sa.Column("usuario_id", sa.String(length=36), nullable=False),
        sa.Column("cliente_nombre", sa.String(length=160), nullable=True),
        sa.Column("cliente_email", sa.String(length=255), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("descuento_total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("impuesto_total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("metodo_pago", sa.String(length=20), nullable=False),
        sa.Column("monto_recibido", sa.Numeric(18, 4), nullable=True),
        sa.Column("cambio", sa.Numeric(18, 4), nullable=True),
        sa.Column("estatus", sa.String(length=20), nullable=False, server_default=sa.text("'pagada'")),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "metodo_pago IN ('efectivo', 'tarjeta', 'transferencia', 'mixto', 'otro')",
            name="ck_venta_metodo_pago",
        ),
        sa.CheckConstraint("estatus IN ('pagada', 'cancelada')", name="ck_venta_estatus"),
        sa.CheckConstraint("subtotal >= 0", name="ck_venta_subtotal_nonnegative"),
        sa.CheckConstraint("descuento_total >= 0", name="ck_venta_descuento_nonnegative"),
        sa.CheckConstraint("impuesto_total >= 0", name="ck_venta_impuesto_nonnegative"),
        sa.CheckConstraint("total >= 0", name="ck_venta_total_nonnegative"),
        sa.CheckConstraint(
            "monto_recibido IS NULL OR monto_recibido >= 0",
            name="ck_venta_monto_recibido_nonnegative",
        ),
        sa.CheckConstraint("cambio IS NULL OR cambio >= 0", name="ck_venta_cambio_nonnegative"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["almacen_id"], ["almacenes.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["cancelled_by_user_id"], ["usuarios.id"]),
        sa.UniqueConstraint("empresa_id", "folio", name="uq_venta_empresa_folio"),
    )
    op.create_index("ix_ventas_empresa_id", "ventas", ["empresa_id"], unique=False)
    op.create_index("ix_ventas_folio", "ventas", ["folio"], unique=False)
    op.create_index("ix_ventas_almacen_id", "ventas", ["almacen_id"], unique=False)
    op.create_index("ix_ventas_usuario_id", "ventas", ["usuario_id"], unique=False)
    op.create_index("ix_ventas_metodo_pago", "ventas", ["metodo_pago"], unique=False)
    op.create_index("ix_ventas_estatus", "ventas", ["estatus"], unique=False)
    op.create_index("ix_ventas_cancelled_by_user_id", "ventas", ["cancelled_by_user_id"], unique=False)

    op.create_table(
        "ventas_detalles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("venta_id", sa.String(length=36), nullable=False),
        sa.Column("material_id", sa.String(length=36), nullable=False),
        sa.Column("sku_snapshot", sa.String(length=80), nullable=False),
        sa.Column("nombre_snapshot", sa.String(length=180), nullable=False),
        sa.Column("cantidad", sa.Numeric(18, 4), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(18, 4), nullable=False),
        sa.Column("descuento_unitario", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("subtotal_linea", sa.Numeric(18, 4), nullable=False),
        sa.Column("total_linea", sa.Numeric(18, 4), nullable=False),
        sa.Column("movimiento_inventario_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint("cantidad > 0", name="ck_venta_detalle_cantidad_positive"),
        sa.CheckConstraint("precio_unitario >= 0", name="ck_venta_detalle_precio_nonnegative"),
        sa.CheckConstraint("descuento_unitario >= 0", name="ck_venta_detalle_descuento_nonnegative"),
        sa.CheckConstraint("subtotal_linea >= 0", name="ck_venta_detalle_subtotal_nonnegative"),
        sa.CheckConstraint("total_linea >= 0", name="ck_venta_detalle_total_nonnegative"),
        sa.ForeignKeyConstraint(["venta_id"], ["ventas.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materiales.id"]),
        sa.ForeignKeyConstraint(["movimiento_inventario_id"], ["movimientos_inventario.id"]),
    )
    op.create_index("ix_ventas_detalles_venta_id", "ventas_detalles", ["venta_id"], unique=False)
    op.create_index("ix_ventas_detalles_material_id", "ventas_detalles", ["material_id"], unique=False)
    op.create_index(
        "ix_ventas_detalles_movimiento_inventario_id",
        "ventas_detalles",
        ["movimiento_inventario_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ventas_detalles_movimiento_inventario_id", table_name="ventas_detalles")
    op.drop_index("ix_ventas_detalles_material_id", table_name="ventas_detalles")
    op.drop_index("ix_ventas_detalles_venta_id", table_name="ventas_detalles")
    op.drop_table("ventas_detalles")

    op.drop_index("ix_ventas_cancelled_by_user_id", table_name="ventas")
    op.drop_index("ix_ventas_estatus", table_name="ventas")
    op.drop_index("ix_ventas_metodo_pago", table_name="ventas")
    op.drop_index("ix_ventas_usuario_id", table_name="ventas")
    op.drop_index("ix_ventas_almacen_id", table_name="ventas")
    op.drop_index("ix_ventas_folio", table_name="ventas")
    op.drop_index("ix_ventas_empresa_id", table_name="ventas")
    op.drop_table("ventas")
