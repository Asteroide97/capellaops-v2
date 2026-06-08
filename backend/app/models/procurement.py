from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Proveedor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "proveedores"

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    razon_social: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rfc: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    contacto_nombre: Mapped[str | None] = mapped_column(String(160), nullable=True)
    correo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    direccion: Mapped[str | None] = mapped_column(Text, nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    empresa = relationship("Empresa")


class Requisicion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "requisiciones"
    __table_args__ = (
        UniqueConstraint("empresa_id", "folio", name="uq_requisicion_empresa_folio"),
        CheckConstraint(
            "estatus IN ('borrador', 'enviada', 'aprobada', 'rechazada', 'cancelada', 'parcial', 'surtida', 'convertida_a_oc')",
            name="ck_requisicion_estatus",
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    folio: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    solicitante_user_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    proveedor_sugerido_id: Mapped[str | None] = mapped_column(ForeignKey("proveedores.id"), nullable=True, index=True)
    orden_compra_id: Mapped[str | None] = mapped_column(ForeignKey("ordenes_compra.id"), nullable=True, index=True)
    es_proyecto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    proyecto_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    proyecto_nombre_snapshot: Mapped[str | None] = mapped_column(String(180), nullable=True)
    prioridad: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", server_default="normal", index=True)
    tarea_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tarea_nombre_snapshot: Mapped[str | None] = mapped_column(String(180), nullable=True)
    partida_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    partida_nombre_snapshot: Mapped[str | None] = mapped_column(String(180), nullable=True)
    aprobador_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    motivo_rechazo: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estatus: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="borrador",
        server_default=text("'borrador'"),
        index=True,
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)

    empresa = relationship("Empresa")
    solicitante_user = relationship("Usuario")
    proveedor_sugerido = relationship("Proveedor")
    orden_compra = relationship("OrdenCompra", back_populates="requisiciones")
    detalles = relationship("RequisicionDetalle", back_populates="requisicion", cascade="all, delete-orphan")


class RequisicionDetalle(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "requisiciones_detalles"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_requisicion_detalle_cantidad_positive"),
        CheckConstraint("cantidad_surtida >= 0", name="ck_requisicion_detalle_surtida_nonnegative"),
    )

    requisicion_id: Mapped[str] = mapped_column(ForeignKey("requisiciones.id"), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materiales.id"), nullable=False, index=True)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cantidad_aprobada: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    cantidad_surtida: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)

    requisicion = relationship("Requisicion", back_populates="detalles")
    material = relationship("Material")


class OrdenCompra(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ordenes_compra"
    __table_args__ = (
        UniqueConstraint("empresa_id", "folio", name="uq_orden_compra_empresa_folio"),
        CheckConstraint(
            "estatus IN ('borrador', 'emitida', 'recibida_parcial', 'recibida', 'cancelada')",
            name="ck_orden_compra_estatus",
        ),
        CheckConstraint("subtotal >= 0", name="ck_orden_compra_subtotal_nonnegative"),
        CheckConstraint("descuento_total >= 0", name="ck_orden_compra_descuento_nonnegative"),
        CheckConstraint("impuesto_total >= 0", name="ck_orden_compra_impuesto_nonnegative"),
        CheckConstraint("total >= 0", name="ck_orden_compra_total_nonnegative"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    folio: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    proveedor_id: Mapped[str] = mapped_column(ForeignKey("proveedores.id"), nullable=False, index=True)
    almacen_destino_id: Mapped[str] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    estatus: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="borrador",
        server_default=text("'borrador'"),
        index=True,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    descuento_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    impuesto_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)

    empresa = relationship("Empresa")
    proveedor = relationship("Proveedor")
    almacen_destino = relationship("Almacen")
    created_by_user = relationship("Usuario")
    detalles = relationship("OrdenCompraDetalle", back_populates="orden_compra", cascade="all, delete-orphan")
    requisiciones = relationship("Requisicion", back_populates="orden_compra")


class OrdenCompraDetalle(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ordenes_compra_detalles"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_orden_compra_detalle_cantidad_positive"),
        CheckConstraint("cantidad_recibida >= 0", name="ck_orden_compra_detalle_recibida_nonnegative"),
        CheckConstraint("costo_unitario >= 0", name="ck_orden_compra_detalle_costo_nonnegative"),
        CheckConstraint("subtotal_linea >= 0", name="ck_orden_compra_detalle_subtotal_nonnegative"),
        CheckConstraint("total_linea >= 0", name="ck_orden_compra_detalle_total_nonnegative"),
    )

    orden_compra_id: Mapped[str] = mapped_column(ForeignKey("ordenes_compra.id"), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materiales.id"), nullable=False, index=True)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cantidad_recibida: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    subtotal_linea: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_linea: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    orden_compra = relationship("OrdenCompra", back_populates="detalles")
    material = relationship("Material")
