from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Plan(TimestampMixin, Base):
    __tablename__ = "planes"
    __table_args__ = (
        CheckConstraint("max_usuarios IS NULL OR max_usuarios > 0", name="ck_plan_max_usuarios_positive"),
        CheckConstraint("max_almacenes IS NULL OR max_almacenes > 0", name="ck_plan_max_almacenes_positive"),
        CheckConstraint(
            "max_facturas_mensuales IS NULL OR max_facturas_mensuales > 0",
            name="ck_plan_max_facturas_positive",
        ),
    )

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    modules: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    max_usuarios: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_almacenes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_facturas_mensuales: Mapped[int | None] = mapped_column(Integer, nullable=True)
    productos_ilimitados: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    ventas_ilimitadas: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    empresas = relationship("Empresa", back_populates="plan")


class Empresa(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "empresas"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    razon_social: Mapped[str | None] = mapped_column(String(180), nullable=True)
    rfc: Mapped[str | None] = mapped_column(String(32), nullable=True)
    giro: Mapped[str | None] = mapped_column(String(120), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email_contacto: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sitio_web: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pais: Mapped[str | None] = mapped_column(String(80), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ciudad: Mapped[str | None] = mapped_column(String(80), nullable=True)
    codigo_postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    direccion: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("planes.code"), nullable=False, index=True)
    access_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    trial_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    plan = relationship("Plan", back_populates="empresas")
    users = relationship("EmpresaUsuario", back_populates="empresa", cascade="all, delete-orphan")
    invitations = relationship("EmpresaUsuarioInvitacion", back_populates="empresa", cascade="all, delete-orphan")
    modules = relationship("EmpresaModulo", back_populates="empresa", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="empresa")


class EmpresaModulo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "empresa_modulos"
    __table_args__ = (UniqueConstraint("empresa_id", "module_name", name="uq_empresa_modulo"),)

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    module_name: Mapped[str] = mapped_column(String(60), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    empresa = relationship("Empresa", back_populates="modules")
