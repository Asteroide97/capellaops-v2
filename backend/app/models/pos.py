from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
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


class Venta(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ventas"
    __table_args__ = (
        UniqueConstraint("empresa_id", "folio", name="uq_venta_empresa_folio"),
        CheckConstraint(
            "metodo_pago IN ('efectivo', 'tarjeta', 'transferencia', 'mixto', 'otro')",
            name="ck_venta_metodo_pago",
        ),
        CheckConstraint("estatus IN ('pagada', 'cancelada')", name="ck_venta_estatus"),
        CheckConstraint("subtotal >= 0", name="ck_venta_subtotal_nonnegative"),
        CheckConstraint("descuento_total >= 0", name="ck_venta_descuento_nonnegative"),
        CheckConstraint("impuesto_total >= 0", name="ck_venta_impuesto_nonnegative"),
        CheckConstraint("total >= 0", name="ck_venta_total_nonnegative"),
        CheckConstraint(
            "monto_recibido IS NULL OR monto_recibido >= 0",
            name="ck_venta_monto_recibido_nonnegative",
        ),
        CheckConstraint("cambio IS NULL OR cambio >= 0", name="ck_venta_cambio_nonnegative"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    folio: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    almacen_id: Mapped[str] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    turno_id: Mapped[str | None] = mapped_column(ForeignKey("pos_turnos_caja.id"), nullable=True, index=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    cliente_nombre: Mapped[str | None] = mapped_column(String(160), nullable=True)
    cliente_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
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
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    detalles = relationship("VentaDetalle", back_populates="venta", cascade="all, delete-orphan")


class VentaDetalle(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ventas_detalles"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_venta_detalle_cantidad_positive"),
        CheckConstraint("precio_unitario >= 0", name="ck_venta_detalle_precio_nonnegative"),
        CheckConstraint("descuento_unitario >= 0", name="ck_venta_detalle_descuento_nonnegative"),
        CheckConstraint("subtotal_linea >= 0", name="ck_venta_detalle_subtotal_nonnegative"),
        CheckConstraint("total_linea >= 0", name="ck_venta_detalle_total_nonnegative"),
    )

    venta_id: Mapped[str] = mapped_column(ForeignKey("ventas.id"), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materiales.id"), nullable=False, index=True)
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
