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
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Almacen(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "almacenes"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="uq_almacen_empresa_codigo"),)

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    codigo: Mapped[str] = mapped_column(String(60), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    empresa = relationship("Empresa")
    existencias = relationship("Existencia", back_populates="almacen", cascade="all, delete-orphan")
    movimientos = relationship("MovimientoInventario", back_populates="almacen")
    transferencias_origen = relationship(
        "TransferenciaInventario",
        back_populates="almacen_origen",
        foreign_keys="TransferenciaInventario.almacen_origen_id",
    )
    transferencias_destino = relationship(
        "TransferenciaInventario",
        back_populates="almacen_destino",
        foreign_keys="TransferenciaInventario.almacen_destino_id",
    )
    conteos = relationship("ConteoInventario", back_populates="almacen")


class Material(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "materiales"
    __table_args__ = (
        UniqueConstraint("empresa_id", "sku", name="uq_material_empresa_sku"),
        CheckConstraint("costo_unitario >= 0", name="ck_material_costo_nonnegative"),
        CheckConstraint("precio_venta >= 0", name="ck_material_precio_nonnegative"),
        CheckConstraint("stock_minimo >= 0", name="ck_material_stock_minimo_nonnegative"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    categoria: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unidad: Mapped[str] = mapped_column(String(40), nullable=False)
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    precio_venta: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    stock_minimo: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    empresa = relationship("Empresa")
    existencias = relationship("Existencia", back_populates="material", cascade="all, delete-orphan")
    movimientos = relationship("MovimientoInventario", back_populates="material")
    transferencia_detalles = relationship("TransferenciaInventarioDetalle", back_populates="material")
    conteo_detalles = relationship("ConteoInventarioDetalle", back_populates="material")


class Existencia(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "existencias"
    __table_args__ = (
        UniqueConstraint("empresa_id", "almacen_id", "material_id", name="uq_existencia_empresa_almacen_material"),
        CheckConstraint("cantidad >= 0", name="ck_existencia_cantidad_nonnegative"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    almacen_id: Mapped[str] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materiales.id"), nullable=False, index=True)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))

    empresa = relationship("Empresa")
    almacen = relationship("Almacen", back_populates="existencias")
    material = relationship("Material", back_populates="existencias")


class MovimientoInventario(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "movimientos_inventario"
    __table_args__ = (
        CheckConstraint("tipo IN ('entrada', 'salida', 'ajuste')", name="ck_movimiento_inventario_tipo"),
        CheckConstraint("cantidad_nueva >= 0", name="ck_movimiento_inventario_cantidad_nueva_nonnegative"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    almacen_id: Mapped[str] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materiales.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cantidad_anterior: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cantidad_nueva: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    referencia_tipo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    referencia_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=utcnow,
    )

    empresa = relationship("Empresa")
    almacen = relationship("Almacen", back_populates="movimientos")
    material = relationship("Material", back_populates="movimientos")
    usuario = relationship("Usuario")


class TransferenciaInventario(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "transferencias_inventario"
    __table_args__ = (
        UniqueConstraint("empresa_id", "folio", name="uq_transferencia_inventario_empresa_folio"),
        CheckConstraint(
            "estatus IN ('borrador', 'confirmada', 'cancelada')",
            name="ck_transferencia_inventario_estatus",
        ),
        CheckConstraint(
            "almacen_origen_id <> almacen_destino_id",
            name="ck_transferencia_inventario_origen_destino_diff",
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    folio: Mapped[str] = mapped_column(String(60), nullable=False)
    almacen_origen_id: Mapped[str] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    almacen_destino_id: Mapped[str] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    estatus: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="borrador",
        server_default=text("'borrador'"),
        index=True,
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    confirmed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    cancelled_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    empresa = relationship("Empresa")
    almacen_origen = relationship(
        "Almacen",
        back_populates="transferencias_origen",
        foreign_keys=[almacen_origen_id],
    )
    almacen_destino = relationship(
        "Almacen",
        back_populates="transferencias_destino",
        foreign_keys=[almacen_destino_id],
    )
    created_by_user = relationship("Usuario", foreign_keys=[created_by_user_id])
    confirmed_by_user = relationship("Usuario", foreign_keys=[confirmed_by_user_id])
    cancelled_by_user = relationship("Usuario", foreign_keys=[cancelled_by_user_id])
    detalles = relationship(
        "TransferenciaInventarioDetalle",
        back_populates="transferencia",
        cascade="all, delete-orphan",
    )


class TransferenciaInventarioDetalle(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "transferencias_inventario_detalles"
    __table_args__ = (
        UniqueConstraint(
            "transferencia_id",
            "material_id",
            name="uq_transferencia_inventario_detalle_transferencia_material",
        ),
        CheckConstraint("cantidad > 0", name="ck_transferencia_inventario_detalle_cantidad_positive"),
        CheckConstraint(
            "costo_unitario_snapshot IS NULL OR costo_unitario_snapshot >= 0",
            name="ck_transferencia_inventario_detalle_costo_nonnegative",
        ),
    )

    transferencia_id: Mapped[str] = mapped_column(
        ForeignKey("transferencias_inventario.id"),
        nullable=False,
        index=True,
    )
    material_id: Mapped[str] = mapped_column(ForeignKey("materiales.id"), nullable=False, index=True)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    costo_unitario_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    transferencia = relationship("TransferenciaInventario", back_populates="detalles")
    material = relationship("Material", back_populates="transferencia_detalles")


class ConteoInventario(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "conteos_inventario"
    __table_args__ = (
        UniqueConstraint("empresa_id", "folio", name="uq_conteo_inventario_empresa_folio"),
        CheckConstraint("estatus IN ('borrador', 'aplicado', 'cancelado')", name="ck_conteo_inventario_estatus"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    almacen_id: Mapped[str] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    folio: Mapped[str] = mapped_column(String(60), nullable=False)
    estatus: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="borrador",
        server_default=text("'borrador'"),
        index=True,
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    applied_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    cancelled_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    empresa = relationship("Empresa")
    almacen = relationship("Almacen", back_populates="conteos")
    created_by_user = relationship("Usuario", foreign_keys=[created_by_user_id])
    applied_by_user = relationship("Usuario", foreign_keys=[applied_by_user_id])
    cancelled_by_user = relationship("Usuario", foreign_keys=[cancelled_by_user_id])
    detalles = relationship("ConteoInventarioDetalle", back_populates="conteo", cascade="all, delete-orphan")


class ConteoInventarioDetalle(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "conteos_inventario_detalles"
    __table_args__ = (
        UniqueConstraint("conteo_id", "material_id", name="uq_conteo_inventario_detalle_conteo_material"),
        CheckConstraint(
            "cantidad_sistema_snapshot >= 0",
            name="ck_conteo_inventario_detalle_sistema_nonnegative",
        ),
        CheckConstraint("cantidad_fisica >= 0", name="ck_conteo_inventario_detalle_fisica_nonnegative"),
    )

    conteo_id: Mapped[str] = mapped_column(ForeignKey("conteos_inventario.id"), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materiales.id"), nullable=False, index=True)
    cantidad_sistema_snapshot: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    cantidad_fisica: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    diferencia: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    ajuste_movimiento_id: Mapped[str | None] = mapped_column(
        ForeignKey("movimientos_inventario.id"),
        nullable=True,
        index=True,
    )

    conteo = relationship("ConteoInventario", back_populates="detalles")
    material = relationship("Material", back_populates="conteo_detalles")
    ajuste_movimiento = relationship("MovimientoInventario")
