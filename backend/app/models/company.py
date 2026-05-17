from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Plan(TimestampMixin, Base):
    __tablename__ = "planes"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    modules: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    empresas = relationship("Empresa", back_populates="plan")


class Empresa(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "empresas"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("planes.code"), nullable=False, index=True)
    access_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    trial_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    plan = relationship("Plan", back_populates="empresas")
    users = relationship("EmpresaUsuario", back_populates="empresa", cascade="all, delete-orphan")
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
