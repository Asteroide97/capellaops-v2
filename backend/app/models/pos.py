from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin, utcnow


class PosTurnoCaja(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "pos_turnos_caja"
    __table_args__ = (
        UniqueConstraint("empresa_id", "folio", name="uq_pos_turno_empresa_folio"),
        CheckConstraint("estatus IN ('abierta', 'cerrada', 'cancelada')", name="ck_pos_turno_estatus"),
        CheckConstraint("fondo_inicial >= 0", name="ck_pos_turno_fondo_inicial_nonnegative"),
        CheckConstraint("total_ventas >= 0", name="ck_pos_turno_total_ventas_nonnegative"),
        CheckConstraint("total_efectivo >= 0", name="ck_pos_turno_total_efectivo_nonnegative"),
        CheckConstraint("total_tarjeta >= 0", name="ck_pos_turno_total_tarjeta_nonnegative"),
        CheckConstraint("total_transferencia >= 0", name="ck_pos_turno_total_transferencia_nonnegative"),
        CheckConstraint("total_otro >= 0", name="ck_pos_turno_total_otro_nonnegative"),
        CheckConstraint("ingresos_manuales >= 0", name="ck_pos_turno_ingresos_nonnegative"),
        CheckConstraint("retiros_manuales >= 0", name="ck_pos_turno_retiros_nonnegative"),
        CheckConstraint(
            "efectivo_contado IS NULL OR efectivo_contado >= 0",
            name="ck_pos_turno_efectivo_contado_nonnegative",
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    almacen_id: Mapped[str] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    folio: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    usuario_apertura_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    usuario_cierre_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    estatus: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="abierta",
        server_default=text("'abierta'"),
        index=True,
    )
    fondo_inicial: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    total_ventas: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    total_efectivo: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    total_tarjeta: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    total_transferencia: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    total_otro: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    ingresos_manuales: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    retiros_manuales: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    efectivo_contado: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    diferencia: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    notas_apertura: Mapped[str | None] = mapped_column(Text, nullable=True)
    notas_cierre: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )

    empresa = relationship("Empresa")
    almacen = relationship("Almacen")
    usuario_apertura = relationship("Usuario", foreign_keys=[usuario_apertura_id])
    usuario_cierre = relationship("Usuario", foreign_keys=[usuario_cierre_id])
    movimientos = relationship("PosTurnoCajaMovimiento", back_populates="turno", cascade="all, delete-orphan")
    ventas = relationship("Venta", back_populates="turno")


class PosTurnoCajaMovimiento(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "pos_turnos_caja_movimientos"
    __table_args__ = (
        CheckConstraint("tipo IN ('ingreso', 'retiro')", name="ck_pos_turno_mov_tipo"),
        CheckConstraint("monto > 0", name="ck_pos_turno_mov_monto_positive"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    turno_id: Mapped[str] = mapped_column(ForeignKey("pos_turnos_caja.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )

    empresa = relationship("Empresa")
    turno = relationship("PosTurnoCaja", back_populates="movimientos")
    usuario = relationship("Usuario")


class PosSettings(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "pos_settings"
    __table_args__ = (
        UniqueConstraint("empresa_id", name="uq_pos_settings_empresa"),
        CheckConstraint(
            "max_discount_percent_without_approval >= 0 AND max_discount_percent_without_approval <= 100",
            name="ck_pos_settings_max_discount_percent_range",
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    max_discount_percent_without_approval: Mapped[Decimal] = mapped_column(
        Numeric(9, 4),
        nullable=False,
        default=Decimal("15"),
        server_default="15",
    )
    allow_negative_margin_without_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    require_approval_below_cost: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )

    empresa = relationship("Empresa")


class Venta(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ventas"
    __table_args__ = (
        UniqueConstraint("empresa_id", "folio", name="uq_venta_empresa_folio"),
        CheckConstraint(
            "metodo_pago IN ('efectivo', 'tarjeta', 'transferencia', 'mixto', 'otro')",
            name="ck_venta_metodo_pago",
        ),
        CheckConstraint("estatus IN ('pagada', 'cancelada', 'suspendida')", name="ck_venta_estatus"),
        CheckConstraint("subtotal >= 0", name="ck_venta_subtotal_nonnegative"),
        CheckConstraint("descuento_lineas_total >= 0", name="ck_venta_descuento_lineas_nonnegative"),
        CheckConstraint("descuento_global >= 0", name="ck_venta_descuento_global_nonnegative"),
        CheckConstraint("descuento_total >= 0", name="ck_venta_descuento_nonnegative"),
        CheckConstraint("impuesto_total >= 0", name="ck_venta_impuesto_nonnegative"),
        CheckConstraint("total >= 0", name="ck_venta_total_nonnegative"),
        CheckConstraint(
            "monto_recibido IS NULL OR monto_recibido >= 0",
            name="ck_venta_monto_recibido_nonnegative",
        ),
        CheckConstraint("cambio IS NULL OR cambio >= 0", name="ck_venta_cambio_nonnegative"),
        CheckConstraint(
            "factura_estado IN ('no_solicitada', 'solicitada', 'pendiente_datos', 'lista_para_facturar', 'facturada', 'cancelada')",
            name="ck_venta_factura_estado",
        ),
        CheckConstraint(
            "factura_revision_estado IS NULL OR factura_revision_estado IN ('pendiente_datos', 'lista_para_facturar', 'en_revision', 'observada', 'preparada', 'descartada')",
            name="ck_venta_factura_revision_estado",
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    folio: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    almacen_id: Mapped[str] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    turno_id: Mapped[str | None] = mapped_column(ForeignKey("pos_turnos_caja.id"), nullable=True, index=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    cliente_nombre: Mapped[str | None] = mapped_column(String(160), nullable=True)
    cliente_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    crm_cliente_id: Mapped[str | None] = mapped_column(ForeignKey("crm_clientes.id"), nullable=True, index=True)
    crm_contacto_id: Mapped[str | None] = mapped_column(ForeignKey("crm_contactos.id"), nullable=True, index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    descuento_lineas_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    descuento_global: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    descuento_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    impuesto_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    metodo_pago: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    monto_recibido: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    cambio: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    estatus: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pagada",
        server_default=text("'pagada'"),
        index=True,
    )
    factura_estado: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="no_solicitada",
        server_default=text("'no_solicitada'"),
        index=True,
    )
    factura_solicitada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    factura_cliente_nombre: Mapped[str | None] = mapped_column(String(160), nullable=True)
    factura_rfc: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    factura_razon_social: Mapped[str | None] = mapped_column(String(200), nullable=True)
    factura_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    factura_crm_cliente_id: Mapped[str | None] = mapped_column(ForeignKey("crm_clientes.id"), nullable=True, index=True)
    factura_crm_contacto_id: Mapped[str | None] = mapped_column(ForeignKey("crm_contactos.id"), nullable=True, index=True)
    factura_uso_cfdi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    factura_regimen_fiscal: Mapped[str | None] = mapped_column(String(10), nullable=True)
    factura_codigo_postal: Mapped[str | None] = mapped_column(String(12), nullable=True)
    factura_notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    factura_revision_estado: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    factura_revision_notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    factura_revisada_por_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=True,
        index=True,
    )
    factura_revisada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    factura_preparada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    factura_descartada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    factura_error_datos: Mapped[str | None] = mapped_column(Text, nullable=True)
    factura_requiere_factura_global: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    empresa = relationship("Empresa")
    almacen = relationship("Almacen")
    turno = relationship("PosTurnoCaja", back_populates="ventas")
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    cancelled_by_user = relationship("Usuario", foreign_keys=[cancelled_by_user_id])
    factura_revisada_por_user = relationship("Usuario", foreign_keys=[factura_revisada_por_user_id])
    crm_cliente = relationship("CRMCliente", foreign_keys=[crm_cliente_id])
    crm_contacto = relationship("CRMContacto", foreign_keys=[crm_contacto_id])
    factura_crm_cliente = relationship("CRMCliente", foreign_keys=[factura_crm_cliente_id])
    factura_crm_contacto = relationship("CRMContacto", foreign_keys=[factura_crm_contacto_id])
    detalles = relationship("VentaDetalle", back_populates="venta", cascade="all, delete-orphan")
    pagos = relationship("VentaPago", back_populates="venta", cascade="all, delete-orphan")
    ajustes = relationship("PosSaleAdjustment", back_populates="venta")
    approvals = relationship("PosSaleApproval", back_populates="venta")


class VentaDetalle(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ventas_detalles"
    __table_args__ = (
        CheckConstraint(
            "tipo_linea IN ('material', 'manual', 'servicio')",
            name="ck_venta_detalle_tipo_linea",
        ),
        CheckConstraint("cantidad > 0", name="ck_venta_detalle_cantidad_positive"),
        CheckConstraint("precio_unitario >= 0", name="ck_venta_detalle_precio_nonnegative"),
        CheckConstraint("descuento_unitario >= 0", name="ck_venta_detalle_descuento_nonnegative"),
        CheckConstraint("impuesto_tasa >= 0", name="ck_venta_detalle_impuesto_tasa_nonnegative"),
        CheckConstraint("impuesto_linea >= 0", name="ck_venta_detalle_impuesto_linea_nonnegative"),
        CheckConstraint("subtotal_linea >= 0", name="ck_venta_detalle_subtotal_nonnegative"),
        CheckConstraint("total_linea >= 0", name="ck_venta_detalle_total_nonnegative"),
        CheckConstraint(
            "("
            "tipo_linea = 'material' AND material_id IS NOT NULL"
            ") OR ("
            "tipo_linea IN ('manual', 'servicio') AND descripcion_manual IS NOT NULL"
            ")",
            name="ck_venta_detalle_linea_requerida",
        ),
    )

    venta_id: Mapped[str] = mapped_column(ForeignKey("ventas.id"), nullable=False, index=True)
    material_id: Mapped[str | None] = mapped_column(ForeignKey("materiales.id"), nullable=True, index=True)
    tipo_linea: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="material",
        server_default=text("'material'"),
        index=True,
    )
    descripcion_manual: Mapped[str | None] = mapped_column(Text, nullable=True)
    es_inventariable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    costo_unitario_manual: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    sku_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    nombre_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    descuento_unitario: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    impuesto_tasa: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    impuesto_linea: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    subtotal_linea: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_linea: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    movimiento_inventario_id: Mapped[str | None] = mapped_column(
        ForeignKey("movimientos_inventario.id"),
        nullable=True,
        index=True,
    )

    venta = relationship("Venta", back_populates="detalles")
    material = relationship("Material")
    movimiento_inventario = relationship("MovimientoInventario")


class VentaPago(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ventas_pagos"
    __table_args__ = (
        CheckConstraint(
            "metodo IN ('efectivo', 'tarjeta', 'transferencia', 'otro')",
            name="ck_venta_pago_metodo",
        ),
        CheckConstraint("monto > 0", name="ck_venta_pago_monto_positive"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    venta_id: Mapped[str] = mapped_column(ForeignKey("ventas.id"), nullable=False, index=True)
    turno_id: Mapped[str | None] = mapped_column(ForeignKey("pos_turnos_caja.id"), nullable=True, index=True)
    metodo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    referencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )

    empresa = relationship("Empresa")
    venta = relationship("Venta", back_populates="pagos")
    turno = relationship("PosTurnoCaja")


class PosSaleAdjustment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "pos_sale_adjustments"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('add_line', 'update_line', 'delete_line', 'recalculate')",
            name="ck_pos_sale_adjustment_tipo",
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    sale_id: Mapped[str] = mapped_column(ForeignKey("ventas.id"), nullable=False, index=True)
    line_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )

    empresa = relationship("Empresa")
    venta = relationship("Venta", back_populates="ajustes")
    usuario = relationship("Usuario")


class PosSaleApproval(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "pos_sale_approvals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_pos_sale_approval_status",
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    sale_id: Mapped[str] = mapped_column(ForeignKey("ventas.id"), nullable=False, index=True)
    requested_by_usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    approved_by_usuario_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    rejected_by_usuario_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )

    empresa = relationship("Empresa")
    venta = relationship("Venta", back_populates="approvals")
    requested_by_usuario = relationship("Usuario", foreign_keys=[requested_by_usuario_id])
    approved_by_usuario = relationship("Usuario", foreign_keys=[approved_by_usuario_id])
    rejected_by_usuario = relationship("Usuario", foreign_keys=[rejected_by_usuario_id])
