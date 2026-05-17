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
