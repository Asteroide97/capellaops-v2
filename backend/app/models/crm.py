from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CRMCliente(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crm_clientes"
    __table_args__ = (
        CheckConstraint("tipo IN ('prospecto', 'cliente', 'otro')", name="ck_crm_cliente_tipo"),
        CheckConstraint("estatus IN ('activo', 'inactivo')", name="ck_crm_cliente_estatus"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    nombre_comercial: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    razon_social: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rfc: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    tipo: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="prospecto",
        server_default=text("'prospecto'"),
        index=True,
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sitio_web: Mapped[str | None] = mapped_column(String(255), nullable=True)
    direccion: Mapped[str | None] = mapped_column(Text, nullable=True)
    ciudad: Mapped[str | None] = mapped_column(String(120), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pais: Mapped[str | None] = mapped_column(String(120), nullable=True)
    codigo_postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    origen: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    industria: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    estatus: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="activo",
        server_default=text("'activo'"),
        index=True,
    )

    empresa = relationship("Empresa")
    contactos = relationship("CRMContacto", back_populates="cliente", cascade="all, delete-orphan")
    oportunidades = relationship("CRMOportunidad", back_populates="cliente", cascade="all, delete-orphan")
    actividades = relationship("CRMActividad", back_populates="cliente")
    cotizaciones = relationship("CRMCotizacion", back_populates="cliente", cascade="all, delete-orphan")


class CRMContacto(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crm_contactos"

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("crm_clientes.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    puesto: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(40), nullable=True)
    principal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0", index=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1", index=True)

    empresa = relationship("Empresa")
    cliente = relationship("CRMCliente", back_populates="contactos")
    oportunidades = relationship("CRMOportunidad", back_populates="contacto")
    actividades = relationship("CRMActividad", back_populates="contacto")
    cotizaciones = relationship("CRMCotizacion", back_populates="contacto")


class CRMOportunidad(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crm_oportunidades"
    __table_args__ = (
        CheckConstraint(
            "etapa IN ('nueva', 'contactado', 'propuesta', 'negociacion', 'ganada', 'perdida')",
            name="ck_crm_oportunidad_etapa",
        ),
        CheckConstraint("monto_estimado >= 0", name="ck_crm_oportunidad_monto_nonnegative"),
        CheckConstraint("probabilidad >= 0 AND probabilidad <= 100", name="ck_crm_oportunidad_probabilidad_range"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("crm_clientes.id"), nullable=False, index=True)
    contacto_id: Mapped[str | None] = mapped_column(ForeignKey("crm_contactos.id"), nullable=True, index=True)
    titulo: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    etapa: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="nueva",
        server_default=text("'nueva'"),
        index=True,
    )
    monto_estimado: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    probabilidad: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    fecha_estimada_cierre: Mapped[date | None] = mapped_column(Date, nullable=True)
    responsable_user_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    origen: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    motivo_perdida: Mapped[str | None] = mapped_column(Text, nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1", index=True)
    cerrada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    empresa = relationship("Empresa")
    cliente = relationship("CRMCliente", back_populates="oportunidades")
    contacto = relationship("CRMContacto", back_populates="oportunidades")
    responsable_user = relationship("Usuario")
    actividades = relationship("CRMActividad", back_populates="oportunidad")
    cotizaciones = relationship("CRMCotizacion", back_populates="oportunidad")


class CRMActividad(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crm_actividades"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('llamada', 'email', 'reunion', 'tarea', 'nota', 'whatsapp', 'otro')",
            name="ck_crm_actividad_tipo",
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    cliente_id: Mapped[str | None] = mapped_column(ForeignKey("crm_clientes.id"), nullable=True, index=True)
    oportunidad_id: Mapped[str | None] = mapped_column(ForeignKey("crm_oportunidades.id"), nullable=True, index=True)
    contacto_id: Mapped[str | None] = mapped_column(ForeignKey("crm_contactos.id"), nullable=True, index=True)
    tipo: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="nota",
        server_default=text("'nota'"),
        index=True,
    )
    titulo: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_actividad: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    fecha_vencimiento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0", index=True)
    completada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usuario_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1", index=True)

    empresa = relationship("Empresa")
    cliente = relationship("CRMCliente", back_populates="actividades")
    oportunidad = relationship("CRMOportunidad", back_populates="actividades")
    contacto = relationship("CRMContacto", back_populates="actividades")
    usuario = relationship("Usuario")


class CRMCotizacion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crm_cotizaciones"
    __table_args__ = (
        UniqueConstraint("empresa_id", "folio", name="uq_crm_cotizacion_empresa_folio"),
        CheckConstraint(
            "estatus IN ('borrador', 'enviada', 'aceptada', 'rechazada', 'cancelada', 'vencida')",
            name="ck_crm_cotizacion_estatus",
        ),
        CheckConstraint("subtotal >= 0", name="ck_crm_cotizacion_subtotal_nonnegative"),
        CheckConstraint("descuento_total >= 0", name="ck_crm_cotizacion_descuento_nonnegative"),
        CheckConstraint("impuesto_total >= 0", name="ck_crm_cotizacion_impuesto_nonnegative"),
        CheckConstraint("total >= 0", name="ck_crm_cotizacion_total_nonnegative"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("crm_clientes.id"), nullable=False, index=True)
    contacto_id: Mapped[str | None] = mapped_column(ForeignKey("crm_contactos.id"), nullable=True, index=True)
    oportunidad_id: Mapped[str | None] = mapped_column(ForeignKey("crm_oportunidades.id"), nullable=True, index=True)
    folio: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    moneda: Mapped[str] = mapped_column(String(10), nullable=False, default="MXN", server_default=text("'MXN'"))
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
    estatus: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="borrador",
        server_default=text("'borrador'"),
        index=True,
    )
    fecha_emision: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    condiciones_pago: Mapped[str | None] = mapped_column(Text, nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    aceptada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rechazada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1", index=True)

    empresa = relationship("Empresa")
    cliente = relationship("CRMCliente", back_populates="cotizaciones")
    contacto = relationship("CRMContacto", back_populates="cotizaciones")
    oportunidad = relationship("CRMOportunidad", back_populates="cotizaciones")
    items = relationship("CRMCotizacionItem", back_populates="cotizacion", cascade="all, delete-orphan")


class CRMCotizacionItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "crm_cotizacion_items"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_crm_cotizacion_item_cantidad_positive"),
        CheckConstraint("precio_unitario >= 0", name="ck_crm_cotizacion_item_precio_nonnegative"),
        CheckConstraint("descuento >= 0", name="ck_crm_cotizacion_item_descuento_nonnegative"),
        CheckConstraint("impuesto_tasa >= 0", name="ck_crm_cotizacion_item_tasa_nonnegative"),
        CheckConstraint("subtotal >= 0", name="ck_crm_cotizacion_item_subtotal_nonnegative"),
        CheckConstraint("impuesto >= 0", name="ck_crm_cotizacion_item_impuesto_nonnegative"),
        CheckConstraint("total >= 0", name="ck_crm_cotizacion_item_total_nonnegative"),
        CheckConstraint("orden >= 0", name="ck_crm_cotizacion_item_orden_nonnegative"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    cotizacion_id: Mapped[str] = mapped_column(ForeignKey("crm_cotizaciones.id"), nullable=False, index=True)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    descuento: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    impuesto_tasa: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    impuesto: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", index=True)

    empresa = relationship("Empresa")
    cotizacion = relationship("CRMCotizacion", back_populates="items")
